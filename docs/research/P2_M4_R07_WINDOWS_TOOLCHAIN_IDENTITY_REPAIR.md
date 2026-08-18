# P2-M4-R07 Windows Toolchain Identity Repair

## Status

- Task: `P2-M4-R07`
- Candidate: `OPENCV_5_0_0_BOUNDED_TRANSITIVE_SOURCE_V2`
- Scope: Windows private synthetic and non-human geometry research only
- State: `PREREGISTERED`

## Trigger evidence

R06 produced two byte-identical Windows clean builds. All five runtime DLL pairs matched, and both
Windows harness runs matched the Linux deterministic digest
`ebfee6e904e75b1cf147a4259904ab53145568d1940f6f272b9e1a595f95b62c`. The OpenCV core build report
nevertheless retained the actual private MSVC, Ninja and Python paths. Configuration also discovered
MinGW through the ambient `PATH` and reported `pthread` as an extra dependency. These facts fail the
frozen private-path and admitted-closure gates even though runtime behavior was deterministic.

The failed and successful R06 roots remain immutable attempt evidence. Their binaries are not
post-processed or promoted.

## Bounded repair

R07 changes only Windows build invocation identity:

- expose the exact existing MSVC, CMake/Ninja and Python tools through temporary canonical junctions
  under `C:\mirror-*`;
- pass exact canonical `CMAKE_C_COMPILER`, `CMAKE_CXX_COMPILER`, `CMAKE_ASM_COMPILER`,
  `CMAKE_MAKE_PROGRAM` and `PYTHON_DEFAULT_EXECUTABLE` values;
- remove the ambient WinGet MinGW directory from child-process `PATH` after the Visual Studio
  environment is imported, while invoking the frozen assembler and build tool by canonical absolute
  path;
- set `WITH_PTHREADS_PF=OFF` so an ambient POSIX thread library cannot enter the Windows closure;
- set `OPENCV_VCSVERSION=unknown`, which truthfully represents the exact release archive and prevents
  the enclosing Project Mirror Git commit from becoming candidate build identity;
- preserve `/experimental:deterministic`, `/pathmap`, `/Brepro`, `/DEBUG:NONE`, all V2 module flags,
  algorithms, fixtures, thresholds and C ABI.

Every canonical path must be absent before the run, must be verified as a junction owned by the
attempt before removal, and must be removed without traversing its target. No source patch, binary
rewrite, dependency, lockfile or runtime code change is allowed.

## Validation gates

- two new Windows clean roots produce byte-identical OpenCV and wrapper DLLs;
- the core build report contains only canonical tool identities and `Version control: unknown`;
- zero actual repository, user profile, WinGet package, attempt-root, PDB or RSDS path remains in any
  runtime DLL;
- imports contain only the admitted OpenCV libraries and standard Windows/MSVC runtime;
- no Winsock, WinHTTP, URLMon, libcurl or other network-capable import enters the closure;
- process-scoped outbound deny plus Filtering Platform capture records zero attempted egress;
- both harness runs match the frozen Linux fixture hashes and all negative controls pass;
- `WITH_PTHREADS_PF=OFF`, no pthread artifact is built or linked, and no other module is added.

Any failure remains `FURTHER_RESEARCH` or requires another separately preregistered bounded repair.
R07 does not approve T05, production, distribution, a project dependency, User Asset processing or
QuestionBank release.
