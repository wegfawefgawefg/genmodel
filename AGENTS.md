# genmodel

C+- style (see ~/Coding/AGENTS.md). Viewer is C++20/SDL3/OpenGL 3.3; generator is Python in gen/.

Never open windows on the user's screen. Render with `scripts/shot.sh` (EGL surfaceless on the real
GPU, no display). `scripts/run.sh` is the user's entry point only.

No test suites. Visual checks with headless captures are the workflow.
