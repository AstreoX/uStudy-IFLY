"""Generate Alpha activation codes for the Alpha internal testing program."""

import asyncio
import secrets
import string
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.database import get_scoped_session
from db.models import ActivationCode


def generate_code() -> str:
    """Generate a single activation code in ALPHA-XXXX-XXXX format."""
    chars = string.ascii_uppercase + string.digits
    part1 = ''.join(secrets.choice(chars) for _ in range(4))
    part2 = ''.join(secrets.choice(chars) for _ in range(4))
    return f"ALPHA-{part1}-{part2}"


async def generate_codes(count: int = 200, validity_days: int = 30) -> list[str]:
    """Generate activation codes and insert them into the database.

    Args:
        count: Number of codes to generate (default: 200)
        validity_days: Validity period in days (default: 30)

    Returns:
        List of generated code strings
    """
    codes = []
    generated_set = set()

    # Generate unique codes
    while len(codes) < count:
        code = generate_code()
        if code not in generated_set:
            generated_set.add(code)
            codes.append(code)

    # Insert into database
    async with get_scoped_session() as session:
        for code in codes:
            activation_code = ActivationCode(
                code=code,
                validity_days=validity_days
            )
            session.add(activation_code)

        await session.commit()
        print(f"Successfully inserted {len(codes)} activation codes into database.")

    return codes


def export_to_csv(codes: list[str], filename: str = "alpha_codes.csv") -> Path:
    """Export codes to a CSV file.

    Args:
        codes: List of activation codes
        filename: Output filename (default: alpha_codes.csv)

    Returns:
        Path to the generated CSV file
    """
    output_path = Path(__file__).parent / filename

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("code,status,validity_days\n")
        for code in codes:
            f.write(f"{code},unused,30\n")

    print(f"Exported {len(codes)} codes to {output_path}")
    return output_path


async def main():
    """Main entry point for the script."""
    print("=" * 50)
    print("Alpha Activation Code Generator")
    print("=" * 50)
    print(f"Generated at: {datetime.now(timezone.utc).isoformat()}")
    print()

    # Generate 200 codes with 30-day validity
    codes = await generate_codes(count=200, validity_days=30)

    # Export to CSV
    export_to_csv(codes)

    print()
    print("=" * 50)
    print("Generation complete!")
    print("=" * 50)
    print()
    print("Sample codes:")
    for code in codes[:5]:
        print(f"  {code}")
    print("  ...")


if __name__ == "__main__":
    asyncio.run(main())
