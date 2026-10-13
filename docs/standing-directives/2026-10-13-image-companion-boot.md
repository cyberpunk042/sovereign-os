# Image companion boot restoration

Operator request (verbatim):

> i restarted my computer and it didn't reload my image companion like the profile would want to, lets investigate and resolve this. it loaded "Nemotron-3-Nano-Omni-30B-Reasoning-NVFP4" instead of qwen-image..

Scope: persist image service definitions and prevent undeclared chat allocations
from falling back to stale defaults on boot. Preserve the selected profile and
the 4090 allocations. Validate without rebooting the workstation.

Verification: companion reapplied successfully; systemctl reports Qwen image
active, enabled, `Transient=no`, Oracle active, Logic inactive. The installed
image unit passes `systemd-analyze verify`; active-profile boot conditions
allow Qwen Image and skip the undeclared Logic allocation. Native `/v1/models`
answers `sd-cpp-local`. Fourteen targeted tests pass. An actual workstation
reboot has not been performed. The separate dual-image activator still uses
its existing transient launch path and is not covered by this companion fix.
