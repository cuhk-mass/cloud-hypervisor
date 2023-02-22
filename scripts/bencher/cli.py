import tap


class GapArgs(tap.Tap):
    ntrials: int = 5
    niters: int = 1


class RedisArgs(tap.Tap):
    from .config import YcsbWorkload

    workload: YcsbWorkload = YcsbWorkload.A


class ManualArgs(tap.Tap):
    cmd: str = ""
    wait: bool = False


class Bench:
    NAME = "bench"
    MANUAL = "manual"
    REDIS = "redis"
    GAP = "gap"


class Args(tap.Tap):
    from .config import LogLevel, VCPUBind

    num: int  # How many VMs to launch
    ncpus: int = 4  # How many vCPUs for each VM
    bind: VCPUBind = VCPUBind.CORE  # Bind guest CPU to certain host node or vCPU
    memory: int = 8 << 30  # How memory in byte for each VM
    dram_ratio: float = 0.2  # Initial DRAM ratio out of all system-ram
    log_level: LogLevel = LogLevel.INFO  # Logging level, defaults to info
    perf_event: str = ""  # Enable perf events collection in guests
    memory_mode: bool = False  # Enable memory mode
    pretty: bool = False  # Enable pretty printing using rich
    no_module: bool = False  # Disable inserting balloon related kernel modules

    def configure(self) -> None:
        # bench: Bench = Bench.MANUAL  # Benchmark to run
        self.add_subparsers(dest=Bench.NAME, help="Which benchmark to run")
        self.add_subparser(Bench.MANUAL, ManualArgs)
        self.add_subparser(Bench.REDIS, RedisArgs)
        self.add_subparser(Bench.GAP, GapArgs)


def main(args: Args):
    from datetime import datetime
    from logging import info
    from pathlib import Path

    from .benchmark.gap import gap_bc
    from .benchmark.redis import redis
    from .benchmark.manual import manual
    from .config import host_cpu_cycler
    from .utils import log
    from .vm import insmod, mount_fs, launch_vms, numa_balancing

    # https://stackoverflow.com/a/44401529
    log(args.log_level, args.pretty)
    info(args)
    ch_out = Path(__file__).parent / "output" / str(datetime.now().isoformat())
    with launch_vms(
        args.num,
        ncpus=args.ncpus,
        memory=args.memory,
        dram_ratio=args.dram_ratio,
        memory_mode=args.memory_mode,
        vcpubind=args.bind,
        cpu_cycler=host_cpu_cycler(),
        output_dir=ch_out,
    ) as vms:
        info("all vm started")
        # mount_fs(vms)
        if not args.no_module:
            insmod(vms)
        numa_balancing(vms, False)
        match getattr(args, Bench.NAME):
            case Bench.MANUAL:
                manual(vms, args.cmd, args.wait)
            case Bench.REDIS:
                info("benchmark to run: redis")
                redis(vms, args.workload, args.ncpus, args.memory_mode, args.perf_event)
                info("benchmark finished: redis")
            case Bench.GAP:
                info("benchmark to run: gap_bc")
                gap_bc(vms, args.ntrials, args.niters)
                info("benchmark finished: gap_bc")
            case _:
                assert False, "Unreachable"
