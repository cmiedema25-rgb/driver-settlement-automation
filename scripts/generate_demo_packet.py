from pathlib import Path

from driver_settlement.demo import generate_demo_dataset


if __name__ == "__main__":
    output = Path("demo_data")
    dataset = generate_demo_dataset(output)
    print(f"Load board: {dataset['load_board']}")
    print(f"Paperwork folder: {output / 'paperwork'}")
    print(f"Generated documents: {len(dataset['documents'])}")
