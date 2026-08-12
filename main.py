import os
import sys
import subprocess
import argparse
from pathlib import Path
from dotenv import load_dotenv

def main():
    # 1. Parse the input PDF argument
    parser = argparse.ArgumentParser(description="OCR Pipeline Orchestrator")
    parser.add_argument("source", help="Path to the SOURCE.pdf file")
    args = parser.parse_args()

    src = args.source
    if not Path(src).is_file():
        print(f"Error: Source file '{src}' not found.")
        sys.exit(1)

    # 2. Load configuration from .env
    load_dotenv()
    workdir = os.environ.get("WORKDIR", "data/raw_images")
    outdir = os.environ.get("OUTDIR", "data/output_docs")
    ingest_dpi = os.environ.get("INGEST_DPI", "200")
    measure_dpi = os.environ.get("MEASURE_DPI", "300")
    refine = os.environ.get("REFINE", "0")
    refine_passes = os.environ.get("REFINE_PASSES", "1")
    
    llm_provider = os.environ.get("LLM_PROVIDER", "groq")
    mid_provider = os.environ.get("MID_PROVIDER", "").strip() or llm_provider
    strong_provider = os.environ.get("STRONG_PROVIDER", "").strip() or "gemini"

    print(f"== config: workdir={workdir} outdir={outdir} dpi={ingest_dpi}/{measure_dpi}  mid={mid_provider} strong={strong_provider} ==")

    py = sys.executable 

    # 3. Dynamic Environment Setup
    # This ensures the scripts in src/pipeline/ can find the modules in src/utils/
    custom_env = os.environ.copy()
    utils_path = str(Path("src/utils").resolve())
    custom_env["PYTHONPATH"] = utils_path + os.pathsep + custom_env.get("PYTHONPATH", "")

    def run_cmd(cmd, allow_fail=False):
        """Helper to run a shell command and handle errors."""
        res = subprocess.run(cmd, env=custom_env)
        if res.returncode != 0 and not allow_fail:
            print(f"\n[ERROR] Pipeline stopped. Command failed: {' '.join(cmd)}")
            sys.exit(res.returncode)

    # 4. Execute the pipeline stages (Notice the updated paths)
    print("== Stage A: ingest ==")
    run_cmd([py, "src/pipeline/01_ingest.py", src, "--workdir", workdir, "--dpi", ingest_dpi])

    print(f"== Stage B: transcribe (mid: {mid_provider}) ==")
    run_cmd([py, "src/pipeline/02_transcribe.py", "--workdir", workdir])

    print(f"== Stage C: correct (mid: {mid_provider}) ==")
    run_cmd([py, "src/pipeline/03_correct.py", "--workdir", workdir])

    print("== Stage G: typography ==")
    run_cmd([py, "src/pipeline/04_typography.py", src, "--workdir", workdir, "--measure-dpi", measure_dpi])

    print("== Stage D+E: assemble ==")
    run_cmd([py, "src/pipeline/05_assemble.py", "--workdir", workdir, "--out", f"{outdir}/output.docx"])

    print("== Stage F: verify ==")
    run_cmd([py, "src/pipeline/06_verify.py", "--workdir", workdir, "--docx", f"{outdir}/output.docx", "--diff"], allow_fail=True)

    # 5. Optional Stage R
    if refine == "1":
        print(f"== Stage R: refine (strong: {strong_provider}) ==")
        run_cmd([py, "src/pipeline/07_refine.py", "--workdir", workdir, "--auto", "--passes", refine_passes, "--out", f"{outdir}/output.docx"])
        
        print("== Stage F: re-verify ==")
        run_cmd([py, "src/pipeline/06_verify.py", "--workdir", workdir, "--docx", f"{outdir}/output.docx", "--diff"], allow_fail=True)

    print(f"\nDONE -> {outdir}/output.docx")

if __name__ == "__main__":
    main()