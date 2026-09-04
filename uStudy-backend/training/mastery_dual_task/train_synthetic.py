"""Train the dual-task mastery model on deterministic synthetic data.

This is a pipeline bootstrap. Metrics are useful for checking learnability and
runtime compatibility, but they must not be reported as real-learner evidence.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np
import torch
from torch.optim import AdamW
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModel, AutoTokenizer, get_linear_schedule_with_warmup

from graph.mastery_dual_task_torch import (
    DualTaskMasteryModel,
    DualTaskTrainingConfig,
    compute_dual_task_loss,
    load_dual_task_checkpoint,
    save_dual_task_checkpoint,
)
from training.mastery_dual_task.synthetic_data import (
    SyntheticSample,
    generate_synthetic_corpus,
    split_by_learner,
    write_synthetic_dataset,
)


class MasteryDataset(Dataset):
    def __init__(self, samples: list[SyntheticSample]) -> None:
        self.samples = samples

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> SyntheticSample:
        return self.samples[index]


class BatchCollator:
    def __init__(self, tokenizer, max_length: int) -> None:
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __call__(self, samples: list[SyntheticSample]) -> dict:
        encoded = self.tokenizer(
            [sample.serialized_text for sample in samples],
            padding=True,
            truncation=True,
            max_length=self.max_length,
            return_tensors="pt",
        )
        return {
            **encoded,
            "current_mastery": torch.tensor(
                [sample.current_mastery for sample in samples], dtype=torch.float32
            ).unsqueeze(-1),
            "relevance_labels": torch.tensor(
                [sample.relevance_label for sample in samples], dtype=torch.long
            ),
            "change_labels": torch.tensor(
                [sample.change_label for sample in samples], dtype=torch.long
            ),
        }


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _move_batch(batch: dict, device: torch.device) -> dict:
    return {key: value.to(device) for key, value in batch.items()}


def _f1(binary_truth: np.ndarray, binary_prediction: np.ndarray, positive: int) -> float:
    truth_positive = binary_truth == positive
    predicted_positive = binary_prediction == positive
    true_positive = int(np.logical_and(truth_positive, predicted_positive).sum())
    false_positive = int(np.logical_and(~truth_positive, predicted_positive).sum())
    false_negative = int(np.logical_and(truth_positive, ~predicted_positive).sum())
    denominator = 2 * true_positive + false_positive + false_negative
    return (2 * true_positive / denominator) if denominator else 0.0


def binary_macro_f1(labels: np.ndarray, probabilities: np.ndarray, threshold: float) -> float:
    predictions = (probabilities >= threshold).astype(np.int64)
    return (_f1(labels, predictions, 0) + _f1(labels, predictions, 1)) / 2.0


def select_relevance_threshold(labels: np.ndarray, probabilities: np.ndarray) -> tuple[float, float]:
    candidates = np.arange(0.05, 0.951, 0.01)
    scored = [
        (binary_macro_f1(labels, probabilities, float(threshold)), float(threshold))
        for threshold in candidates
    ]
    best_score, best_threshold = max(scored, key=lambda item: (item[0], -abs(item[1] - 0.55)))
    return round(best_threshold, 2), best_score


def _change_metrics(
    relevance_labels: np.ndarray,
    change_labels: np.ndarray,
    change_predictions: np.ndarray,
) -> dict[str, float]:
    mask = relevance_labels == 1
    if not mask.any():
        return {"change_accuracy": 0.0, "change_mae_points": 0.0}
    truth = change_labels[mask]
    predicted = change_predictions[mask]
    return {
        "change_accuracy": float((truth == predicted).mean()),
        "change_mae_points": float(np.abs(truth - predicted).mean() * 5.0),
    }


@torch.inference_mode()
def evaluate(
    model: DualTaskMasteryModel,
    data_loader: DataLoader,
    device: torch.device,
    *,
    threshold: float,
    use_amp: bool,
) -> dict:
    model.eval()
    losses: list[float] = []
    relevance_probabilities: list[float] = []
    relevance_labels: list[int] = []
    change_labels: list[int] = []
    change_predictions: list[int] = []
    for batch in data_loader:
        batch = _move_batch(batch, device)
        with torch.cuda.amp.autocast(enabled=use_amp):
            relevance_logits, change_logits = model(
                input_ids=batch["input_ids"],
                attention_mask=batch["attention_mask"],
                token_type_ids=batch.get("token_type_ids"),
                current_mastery=batch["current_mastery"],
            )
            total_loss, _, _ = compute_dual_task_loss(
                relevance_logits,
                change_logits,
                batch["relevance_labels"],
                batch["change_labels"],
            )
        losses.append(float(total_loss.item()))
        relevance_probabilities.extend(
            torch.sigmoid(relevance_logits).squeeze(-1).cpu().tolist()
        )
        relevance_labels.extend(batch["relevance_labels"].cpu().tolist())
        change_labels.extend(batch["change_labels"].cpu().tolist())
        change_predictions.extend((change_logits.argmax(dim=-1) - 2).cpu().tolist())

    labels_array = np.asarray(relevance_labels, dtype=np.int64)
    probabilities_array = np.asarray(relevance_probabilities, dtype=np.float64)
    relevance_predictions = (probabilities_array >= threshold).astype(np.int64)
    metrics = {
        "loss": float(np.mean(losses)) if losses else 0.0,
        "node_macro_f1": binary_macro_f1(labels_array, probabilities_array, threshold),
        "relevant_f1": _f1(labels_array, relevance_predictions, 1),
        "node_accuracy": float((labels_array == relevance_predictions).mean()),
        "relevance_labels": labels_array,
        "relevance_probabilities": probabilities_array,
    }
    metrics.update(
        _change_metrics(
            labels_array,
            np.asarray(change_labels, dtype=np.int64),
            np.asarray(change_predictions, dtype=np.int64),
        )
    )
    return metrics


def _json_metrics(metrics: dict) -> dict:
    return {
        key: value
        for key, value in metrics.items()
        if key not in {"relevance_labels", "relevance_probabilities"}
    }


def train(args: argparse.Namespace) -> dict:
    config = DualTaskTrainingConfig(
        encoder_checkpoint=args.model,
        batch_size=args.batch_size,
        max_sequence_length=args.max_length,
        epochs=args.epochs,
        random_seeds=(args.seed,),
    )
    set_seed(args.seed)
    output_root = Path(args.output_dir)
    data_dir = output_root / "synthetic_data"
    checkpoint_dir = output_root / "checkpoint"
    output_root.mkdir(parents=True, exist_ok=True)

    samples = generate_synthetic_corpus(seed=args.seed)
    splits = split_by_learner(samples, seed=args.seed)
    manifest = write_synthetic_dataset(data_dir, splits)

    if args.smoke:
        splits = {
            "train": splits["train"][: args.smoke_train_samples],
            "validation": splits["validation"][: args.smoke_validation_samples],
            "test": splits["test"][: args.smoke_validation_samples],
        }

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    encoder = AutoModel.from_pretrained(args.model)
    model = DualTaskMasteryModel(
        encoder=encoder,
        hidden_size=int(encoder.config.hidden_size),
        dropout=config.dropout,
    )
    if args.freeze_encoder:
        for parameter in model.encoder.parameters():
            parameter.requires_grad = False

    device = torch.device(args.device)
    model.to(device)
    use_amp = device.type == "cuda"
    collator = BatchCollator(tokenizer, args.max_length)
    train_loader = DataLoader(
        MasteryDataset(splits["train"]),
        batch_size=args.batch_size,
        shuffle=True,
        collate_fn=collator,
        num_workers=0,
    )
    validation_loader = DataLoader(
        MasteryDataset(splits["validation"]),
        batch_size=args.batch_size,
        shuffle=False,
        collate_fn=collator,
        num_workers=0,
    )
    test_loader = DataLoader(
        MasteryDataset(splits["test"]),
        batch_size=args.batch_size,
        shuffle=False,
        collate_fn=collator,
        num_workers=0,
    )

    trainable_parameters = [parameter for parameter in model.parameters() if parameter.requires_grad]
    optimizer = AdamW(
        trainable_parameters,
        lr=config.learning_rate,
        weight_decay=config.weight_decay,
    )
    planned_steps = max(1, len(train_loader) * args.epochs)
    if args.max_steps:
        planned_steps = min(planned_steps, args.max_steps)
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=max(1, math.ceil(planned_steps * 0.1)),
        num_training_steps=planned_steps,
    )
    scaler = torch.cuda.amp.GradScaler(enabled=use_amp)

    history: list[dict] = []
    best_validation_loss = float("inf")
    best_epoch = 0
    global_step = 0
    started_at = time.time()
    for epoch in range(1, args.epochs + 1):
        model.train()
        epoch_losses: list[float] = []
        for batch in train_loader:
            batch = _move_batch(batch, device)
            optimizer.zero_grad(set_to_none=True)
            with torch.cuda.amp.autocast(enabled=use_amp):
                relevance_logits, change_logits = model(
                    input_ids=batch["input_ids"],
                    attention_mask=batch["attention_mask"],
                    token_type_ids=batch.get("token_type_ids"),
                    current_mastery=batch["current_mastery"],
                )
                total_loss, _, _ = compute_dual_task_loss(
                    relevance_logits,
                    change_logits,
                    batch["relevance_labels"],
                    batch["change_labels"],
                    change_loss_weight=config.change_loss_weight,
                )
            scaler.scale(total_loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(trainable_parameters, max_norm=1.0)
            scaler.step(optimizer)
            scaler.update()
            scheduler.step()
            epoch_losses.append(float(total_loss.item()))
            global_step += 1
            if global_step % args.log_every == 0 or global_step == planned_steps:
                print(
                    json.dumps(
                        {
                            "event": "train_step",
                            "epoch": epoch,
                            "step": global_step,
                            "planned_steps": planned_steps,
                            "loss": round(float(np.mean(epoch_losses[-args.log_every :])), 4),
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
            if args.max_steps and global_step >= args.max_steps:
                break

        validation_metrics = evaluate(
            model,
            validation_loader,
            device,
            threshold=0.55,
            use_amp=use_amp,
        )
        epoch_record = {
            "epoch": epoch,
            "train_loss": float(np.mean(epoch_losses)) if epoch_losses else 0.0,
            "validation": _json_metrics(validation_metrics),
        }
        history.append(epoch_record)
        print(json.dumps({"event": "epoch_end", **epoch_record}, ensure_ascii=False), flush=True)

        if validation_metrics["loss"] < best_validation_loss:
            best_validation_loss = validation_metrics["loss"]
            best_epoch = epoch
            save_dual_task_checkpoint(model, tokenizer, checkpoint_dir)
        if epoch - best_epoch >= config.early_stopping_patience:
            print(json.dumps({"event": "early_stopping", "epoch": epoch}), flush=True)
            break
        if args.max_steps and global_step >= args.max_steps:
            break

    best_model, reloaded_tokenizer = load_dual_task_checkpoint(
        checkpoint_dir,
        device=str(device),
    )
    validation_metrics = evaluate(
        best_model,
        validation_loader,
        device,
        threshold=0.55,
        use_amp=use_amp,
    )
    selected_threshold, selected_macro_f1 = select_relevance_threshold(
        validation_metrics["relevance_labels"],
        validation_metrics["relevance_probabilities"],
    )
    test_metrics = evaluate(
        best_model,
        test_loader,
        device,
        threshold=selected_threshold,
        use_amp=use_amp,
    )

    smoke_text = splits["test"][0].serialized_text
    smoke_tokens = reloaded_tokenizer(
        [smoke_text],
        return_tensors="pt",
        truncation=True,
        max_length=args.max_length,
    )
    smoke_tokens = {key: value.to(device) for key, value in smoke_tokens.items()}
    smoke_mastery = torch.tensor(
        [[float(splits["test"][0].current_mastery)]], device=device
    )
    with torch.inference_mode():
        smoke_relevance, smoke_change = best_model(
            current_mastery=smoke_mastery,
            **smoke_tokens,
        )

    summary = {
        "synthetic_only": True,
        "mode": "smoke" if args.smoke else "gpu_train",
        "device": str(device),
        "torch_version": torch.__version__,
        "config": asdict(config),
        "effective": {
            "max_length": args.max_length,
            "batch_size": args.batch_size,
            "epochs_requested": args.epochs,
            "global_steps": global_step,
            "encoder_frozen": args.freeze_encoder,
        },
        "data_manifest": manifest,
        "history": history,
        "best_epoch": best_epoch,
        "selected_relevance_threshold": selected_threshold,
        "selected_validation_macro_f1": selected_macro_f1,
        "validation_metrics_at_055": _json_metrics(validation_metrics),
        "test_metrics": _json_metrics(test_metrics),
        "checkpoint_reload_smoke": {
            "relevance_shape": list(smoke_relevance.shape),
            "change_shape": list(smoke_change.shape),
        },
        "elapsed_seconds": round(time.time() - started_at, 2),
    }
    (output_root / "training_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({"event": "training_complete", **summary}, ensure_ascii=False), flush=True)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--model", default="google-bert/bert-base-chinese")
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--max-length", type=int, default=160)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-steps", type=int, default=0)
    parser.add_argument("--log-every", type=int, default=25)
    parser.add_argument("--freeze-encoder", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--smoke-train-samples", type=int, default=8)
    parser.add_argument("--smoke-validation-samples", type=int, default=8)
    args = parser.parse_args()
    if args.device == "cuda" and not torch.cuda.is_available():
        parser.error("CUDA was requested but is not available")
    return args


if __name__ == "__main__":
    train(parse_args())
