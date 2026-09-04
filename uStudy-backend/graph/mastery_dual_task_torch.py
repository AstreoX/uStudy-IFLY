"""PyTorch model and loss for paper-style dual-task mastery assessment.

This module is imported only when a trained checkpoint is enabled. A checkpoint
directory contains ``encoder/`` and ``tokenizer/`` Hugging Face artifacts plus
``dual_task_heads.pt`` for the two task heads.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import torch
from torch import nn
from torch.nn import functional as F


@dataclass(frozen=True)
class DualTaskTrainingConfig:
    """Frozen SI Table S1 defaults for the next training step."""

    encoder_checkpoint: str = "google-bert/bert-base-chinese"
    learning_rate: float = 2e-5
    batch_size: int = 16
    max_sequence_length: int = 512
    epochs: int = 5
    weight_decay: float = 0.01
    dropout: float = 0.1
    change_loss_weight: float = 1.0
    random_seeds: tuple[int, ...] = (42, 52, 62, 72, 82)
    early_stopping_patience: int = 2
    relevance_threshold: float = 0.55


class DualTaskMasteryModel(nn.Module):
    """Shared Transformer encoder with relevance and five-class change heads."""

    def __init__(self, encoder: nn.Module, hidden_size: int, dropout: float = 0.1) -> None:
        super().__init__()
        self.encoder = encoder
        self.dropout = nn.Dropout(dropout)
        self.relevance_head = nn.Linear(hidden_size, 1)
        self.change_head = nn.Linear(hidden_size + 1, 5)

    @classmethod
    def from_encoder_path(cls, encoder_path: str | Path, dropout: float = 0.1):
        from transformers import AutoModel

        encoder = AutoModel.from_pretrained(str(encoder_path), local_files_only=True)
        hidden_size = int(encoder.config.hidden_size)
        return cls(encoder=encoder, hidden_size=hidden_size, dropout=dropout)

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor,
        current_mastery: torch.Tensor,
        token_type_ids: torch.Tensor | None = None,
        **encoder_kwargs,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        encoder_inputs = {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            **encoder_kwargs,
        }
        if token_type_ids is not None:
            encoder_inputs["token_type_ids"] = token_type_ids
        outputs = self.encoder(**encoder_inputs)
        turn_node_representation = self.dropout(outputs.last_hidden_state[:, 0, :])
        relevance_logits = self.relevance_head(turn_node_representation)
        change_features = torch.cat((turn_node_representation, current_mastery), dim=-1)
        change_logits = self.change_head(change_features)
        return relevance_logits, change_logits


def compute_dual_task_loss(
    relevance_logits: torch.Tensor,
    change_logits: torch.Tensor,
    relevance_labels: torch.Tensor,
    change_labels: torch.Tensor,
    *,
    change_loss_weight: float = 1.0,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Compute ``L_node + lambda * L_change`` exactly as defined in the paper.

    Binary cross-entropy is averaged over every candidate pair. Five-class cross-
    entropy is averaged only over pairs whose relevance label equals one. Change
    labels use the paper's codes ``-2..+2`` and are shifted to ``0..4`` only for
    PyTorch cross-entropy. A batch without relevant pairs contributes a
    differentiable zero change loss.
    """

    if change_loss_weight < 0:
        raise ValueError("change_loss_weight must be non-negative")
    node_loss = F.binary_cross_entropy_with_logits(
        relevance_logits.squeeze(-1), relevance_labels.float()
    )
    relevant_mask = relevance_labels.bool()
    if relevant_mask.any():
        relevant_change_labels = change_labels[relevant_mask].long()
        if ((relevant_change_labels < -2) | (relevant_change_labels > 2)).any():
            raise ValueError("Relevant mastery-change labels must be between -2 and +2")
        change_loss = F.cross_entropy(
            change_logits[relevant_mask], relevant_change_labels + 2
        )
    else:
        change_loss = change_logits.sum() * 0.0
    total_loss = node_loss + change_loss_weight * change_loss
    return total_loss, node_loss, change_loss


def load_dual_task_checkpoint(
    checkpoint_path: str | Path,
    *,
    device: str = "cpu",
) -> tuple[DualTaskMasteryModel, object]:
    """Load an encoder/tokenizer and the two trained task heads."""

    from transformers import AutoTokenizer

    checkpoint = Path(checkpoint_path)
    encoder_path = checkpoint / "encoder"
    tokenizer_path = checkpoint / "tokenizer"
    heads_path = checkpoint / "dual_task_heads.pt"
    for required in (encoder_path, tokenizer_path, heads_path):
        if not required.exists():
            raise FileNotFoundError(f"Incomplete dual-task checkpoint, missing: {required}")

    model = DualTaskMasteryModel.from_encoder_path(encoder_path)
    try:
        head_state = torch.load(heads_path, map_location="cpu", weights_only=True)
    except TypeError:  # PyTorch < 2.0 compatibility
        head_state = torch.load(heads_path, map_location="cpu")
    model.relevance_head.load_state_dict(head_state["relevance_head"])
    model.change_head.load_state_dict(head_state["change_head"])
    model.to(device)
    model.eval()
    tokenizer = AutoTokenizer.from_pretrained(str(tokenizer_path), local_files_only=True)
    return model, tokenizer


def save_dual_task_checkpoint(
    model: DualTaskMasteryModel,
    tokenizer,
    checkpoint_path: str | Path,
) -> None:
    """Persist artifacts in the format consumed by the runtime adapter."""

    checkpoint = Path(checkpoint_path)
    encoder_path = checkpoint / "encoder"
    tokenizer_path = checkpoint / "tokenizer"
    checkpoint.mkdir(parents=True, exist_ok=True)
    model.encoder.save_pretrained(encoder_path)
    tokenizer.save_pretrained(tokenizer_path)
    torch.save(
        {
            "relevance_head": model.relevance_head.state_dict(),
            "change_head": model.change_head.state_dict(),
        },
        checkpoint / "dual_task_heads.pt",
    )
