# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
from pathlib import Path

import utilities


def main() -> int:
    parser = argparse.ArgumentParser(description="Run CERA FDK reconstruction from a config file.")
    parser.add_argument("--config", required=True, help="Rendered CERA config file path")
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    if not config_path.exists():
        print(f"ERROR: Config file not found: {config_path}", flush=True)
        return 1

    pipeline = None

    try:
        import cerapy  # keep import here so it happens inside the CERA environment

        print(f"* Use config file:", flush=True)
        print(str(config_path), flush=True)

        print("* Create FDK pipeline...", flush=True)
        pipeline = cerapy.PipelineFdk(cerapy.DataType.Float)
        print("OK", flush=True)

        print("* Configure pipeline...", flush=True)
        pipeline.configureFromFile(str(config_path))
        print("OK", flush=True)

        with utilities.timer("FDK config file"):
            print("* Start pipeline...", flush=True)
            pipeline.start()
            print("OK", flush=True)

            print("* Processing...", flush=True)
            num_projections = pipeline.getNumProjectionsOnGeometrySegment(0)
            projection_paths = pipeline.getProjectionPaths(num_projections)

            for i in range(num_projections):
                pipeline.readAndInputProjection(0, i)
                try:
                    print(projection_paths[i], flush=True)
                except Exception:
                    print(f"projection_{i}", flush=True)

            print("OK", flush=True)

            print("* Stop pipeline...", flush=True)
            pipeline.stop()
            print("OK", flush=True)

        print("* Write volume...", flush=True)
        pipeline.downloadVolumeToFileFromConfig()
        print("OK", flush=True)

        print("* Cleanup...", flush=True)
        del pipeline
        print("OK", flush=True)

        return 0

    except RuntimeError as rte:
        print()
        utilities.handleCeraException(rte, pipeline)
        print("\n* Cleanup...", flush=True)
        if pipeline is not None:
            try:
                del pipeline
            except Exception:
                pass
        print("OK", flush=True)
        return 1

    except Exception as e:
        print(f"Unexpected error: {e}", flush=True)
        if pipeline is not None:
            try:
                utilities.printCeraErrors(pipeline)
            except Exception:
                pass
            try:
                del pipeline
            except Exception:
                pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())