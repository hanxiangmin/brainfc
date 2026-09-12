"""Auditable external raw-data adapters; no spatial preprocessing is simulated."""

from dataclasses import dataclass
from pathlib import Path
import re
import shlex
import shutil
import subprocess
from .models import InputError


@dataclass
class CommandPlan:
    """An external command represented as argv and a human description.

    argv is list[str]; description is str. Construction itself does not execute
    anything. Plans from this module bind original BIDS and license read-only.
    Calling run explicitly executes the command and may download Docker images
    or templates; these dependencies are not bundled in the pip distribution."""

    argv: list[str]
    description: str

    def to_dict(self):
        # PowerShell has different quoting from cmd.exe and POSIX shells.
        """Return argv, description, powershell and posix command renderings.

        Shell renderings are for review/pasting. run executes argv with shell=False,
        so paths and arguments are not interpolated into a shell command."""
        powershell = "& " + " ".join("'" + s.replace("'", "''") + "'" for s in self.argv)
        return {
            "argv": self.argv,
            "powershell": powershell,
            "posix": shlex.join(self.argv),
            "description": self.description,
        }

    def run(self, *, log=None):
        """Execute argv synchronously, optionally writing a new combined log.

        log is None (inherit terminal output), or a new filename whose parent exists.
        Returns subprocess.CompletedProcess after a successful exit. Raises InputError
        if the executable is missing, FileExistsError if log exists, or
        subprocess.CalledProcessError when the external program exits unsuccessfully.
        No timeout or automatic retry is applied."""
        if not shutil.which(self.argv[0]):
            raise InputError(f"External executable not installed: {self.argv[0]}")
        if log:
            with Path(log).open("x", encoding="utf-8") as f:
                return subprocess.run(self.argv, shell=False, stdout=f, stderr=subprocess.STDOUT, check=True)
        return subprocess.run(self.argv, shell=False, check=True)


def _input_directory(path):
    p = Path(path).expanduser().resolve()
    if not p.is_dir():
        raise InputError(f"Input directory does not exist: {p}")
    return p


def _separate(input_dir, output_dir):
    if input_dir == output_dir or input_dir in output_dir.parents or output_dir in input_dir.parents:
        raise InputError("Use a separate output directory outside the source tree.")


def dicom_plan(source, output, *, executable="dcm2niix"):
    """Plan dcm2niix conversion without running it or creating output.

    source is an existing DICOM directory; output must be new and outside source
    (neither directory can contain the other). executable defaults to 'dcm2niix'.
    Returns CommandPlan with JSON output, anonymized sidecars and gzipped NIfTI.
    InputError reports invalid directories. Planning does not test executable
    availability. Output filenames are series-based and are not automatically BIDS."""
    source = _input_directory(source)
    output = Path(output).expanduser().resolve()
    _separate(source, output)
    if output.exists():
        raise InputError("DICOM conversion output must be a new directory.")
    return CommandPlan(
        [executable, "-b", "y", "-ba", "y", "-z", "y", "-f", "%s_%p", "-o", str(output), str(source)],
        "DICOM → NIfTI + JSON. Afterwards verify series identity and organize BIDS; filenames are not automatically BIDS-compliant.",
    )


def convert_dicom(source, output, *, executable="dcm2niix", log=None):
    """Create a new output directory and run dcm2niix synchronously.

    source/output/executable follow dicom_plan; log follows CommandPlan.run.
    Returns subprocess.CompletedProcess. Checks executable availability before
    creating output. External failure may leave partial conversion files; choose
    a new destination to retry. Conversion does not organize or validate BIDS."""
    plan = dicom_plan(source, output, executable=executable)
    if not shutil.which(executable):
        raise InputError("Install the external dcm2niix executable first.")
    Path(output).mkdir(parents=True, exist_ok=False)
    return plan.run(log=log)


def fmriprep_plan(
    bids_dir,
    output_dir,
    license_file,
    *,
    participant=None,
    space="MNI152NLin6Asym",
    image="nipreps/fmriprep:25.2.5",
):
    """Build a pinned Docker fMRIPrep invocation without running it.

    Parameters
    ----------
    bids_dir : str or pathlib.Path
        Existing raw BIDS root containing dataset_description.json.
    output_dir : str or pathlib.Path
        Derivatives directory outside source; may already exist for resuming.
    license_file : str or pathlib.Path
        Existing FreeSurfer license, mounted read-only.
    participant : str or None, default None
        One alphanumeric subject label, with optional 'sub-' prefix; None processes
        all subjects. A specified subject directory must exist.
    space : str, default 'MNI152NLin6Asym'
        Alphanumeric named template; output requested at res-2.
    image : str, default 'nipreps/fmriprep:25.2.5'
        Must be a pinned numeric nipreps/fmriprep:X.Y.Z image.

    Returns
    -------
    CommandPlan
        Docker command using --fs-no-reconall and one output space.

    Notes
    -----
    Requires Docker Linux containers, license, CPU/RAM and template/image downloads
    when run. This planner performs only basic path checks. The web route additionally
    calls check_raw_bids; fMRIPrep performs full BIDS validation. Inspect external
    reports before extraction. No DICOM-to-BIDS inference or surface reconstruction."""
    bids = _input_directory(bids_dir)
    out = Path(output_dir).expanduser().resolve()
    _separate(bids, out)
    license_path = Path(license_file).expanduser().resolve()
    if not (bids / "dataset_description.json").is_file():
        raise InputError("BIDS input requires dataset_description.json and subject anat/func directories.")
    if not license_path.is_file():
        raise InputError("FreeSurfer license file is missing.")
    if not re.fullmatch(r"[A-Za-z0-9]+", space):
        raise InputError("Use a named template space, e.g. MNI152NLin6Asym or MNIColin27.")
    if not re.fullmatch(r"nipreps/fmriprep:[0-9]+\.[0-9]+\.[0-9]+", image):
        raise InputError("Pin the fMRIPrep image to a numeric release tag.")
    argv = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{bids}:/data:ro",
        "-v",
        f"{out}:/out",
        "-v",
        f"{license_path}:/license.txt:ro",
        image,
        "/data",
        "/out",
        "participant",
        "--fs-license-file",
        "/license.txt",
        "--fs-no-reconall",
        "--output-spaces",
        space + ":res-2",
    ]
    if participant:
        subject = participant.removeprefix("sub-")
        if not re.fullmatch(r"[A-Za-z0-9]+", subject):
            raise InputError("participant must be an alphanumeric BIDS subject label.")
        if not (bids / f"sub-{subject}").is_dir():
            raise InputError("Selected participant is not present in the BIDS directory.")
        argv.extend(["--participant-label", subject])
    return CommandPlan(
        argv,
        "Raw BIDS BOLD + T1 → fMRIPrep derivatives. Requires Docker (Linux containers), FreeSurfer license, template downloads and sufficient CPU/RAM. Inspect fMRIPrep reports before extraction.",
    )
