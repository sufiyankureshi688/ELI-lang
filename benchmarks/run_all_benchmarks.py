#!/usr/bin/env python3
import os
import subprocess
import time
import csv
import sys

# -------------------------
# CONFIG
# -------------------------

INTERP = "src/alpha_i2.py"
COMP = "src/alpha_c2.py"
ARCH = "arm64"

OUTDIR = "benchmarks/sum_scaled"
NS = [
    10_000,
    100_000,
    1_000_000,
    2_000_000,
    5_000_000
]

# -------------------------
# UTILS
# -------------------------

def run(cmd):
    """Run shell command and return elapsed time"""
    start = time.time()
    subprocess.run(
        cmd,
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True
    )
    return time.time() - start


def compile_native(src, out):
    """Compile ELI file to native binary if missing"""
    if os.path.exists(out):
        return
    print(f"[compile] {src} → {out}")
    cmd = f"{sys.executable} {COMP} {src} -a {ARCH} -o {out}"
    subprocess.run(cmd, shell=True, check=True)


def gen_sum_program(filename, N):
    """
    Generate sum-of-N benchmark using same structure as user’s sumofmillion.
    N = k*1000 to keep J-offsets unchanged.
    """
    k = N // 1000
    if k * 1000 != N:
        raise ValueError(f"N={N} must be divisible by 1000 (for structure preservation).")

    content = f"""\
{k} 1000 M 1000 T
0 1001 T
0 1002 T
1002 F 1000 F L 16 Z
1002 F 1 A 1002 T
1001 F 1002 F A 1001 T
-21 J
1001 F P 10 O H
"""

    with open(filename, "w") as f:
        f.write(content)


# -------------------------
# MAIN
# -------------------------

def main():
    os.makedirs(OUTDIR, exist_ok=True)

    results = []

    for N in NS:
        name = f"sum_{N}"
        eli_path = f"{OUTDIR}/{name}.eli"
        bin_path = f"{OUTDIR}/{name}"

        print(f"\n=== Generating {name} ===")
        gen_sum_program(eli_path, N)

        compile_native(eli_path, bin_path)

        interp_cmd = f"{sys.executable} {INTERP} {eli_path}"
        native_cmd = f"./{bin_path}"

        # Run interpreter once (heavy workloads)
        t_interp = run(interp_cmd)
        t_native = run(native_cmd)

        speed = t_interp / t_native if t_native > 0 else float("inf")

        results.append((name, N, t_interp, t_native, speed))

        print(f"{name}: interp={t_interp:.6f}s native={t_native:.6f}s speedup={speed:.2f}x")

    # Write CSV
    with open("sum_scaling_results.csv", "w") as f:
        w = csv.writer(f)
        w.writerow(["name", "N", "interp_time", "native_time", "speedup"])
        for row in results:
            w.writerow(row)

    print("\nSaved: sum_scaling_results.csv")


if __name__ == "__main__":
    main()
