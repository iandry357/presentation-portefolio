import shutil
from pathlib import Path

SRC = Path(r"C:\Users\iandr\.cache\huggingface\hub\models--Qwen--Qwen2.5-1.5B-Instruct\snapshots\989aa7980e4cf806f80c7fef2b1adb7bc71aa306")

DST = Path(__file__).parent.parent / "training" / "models" / "qwen-base"

FILES = [
    "config.json",
    "generation_config.json",
    "model.safetensors",
    "tokenizer.json",
    "tokenizer_config.json",
    "merges.txt",
    "vocab.json",
]

def main():
    DST.mkdir(parents=True, exist_ok=True)
    print(f"Destination : {DST}\n")

    for fname in FILES:
        src_file = SRC / fname
        dst_file = DST / fname

        if not src_file.exists():
            print(f"  [SKIP] {fname} — introuvable dans le cache")
            continue

        size_mb = src_file.stat().st_size / (1024 * 1024)
        print(f"  Copie {fname} ({size_mb:.1f} Mo)...")
        shutil.copy2(src_file, dst_file)
        print(f"  [OK]   {fname}")

    print(f"\nTermine. Fichiers dans : {DST}")

if __name__ == "__main__":
    main()