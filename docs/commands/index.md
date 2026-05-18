# Command Reference

All commands accept `--help` for detailed option descriptions.

| Command | Category | Description |
|---|---|---|
| [`newmod`](scaffolding.md#newmod) | Scaffolding | Scaffold a new OOT project |
| [`newgroup`](scaffolding.md#newgroup) | Scaffolding | Add a block group directory |
| [`newblock`](blocks.md#newblock) | Block lifecycle | Generate a block header, test, and build entries |
| [`newparam`](blocks.md#newparam) | Block lifecycle | Add an `Annotated<>` parameter to a block |
| [`cp`](blocks.md#cp) | Block lifecycle | Copy a block to a new name |
| [`mv`](blocks.md#mv) | Block lifecycle | Move a block to a different group |
| [`rename`](blocks.md#rename) | Block lifecycle | Rename a block everywhere |
| [`rm`](blocks.md#rm) | Block lifecycle | Remove a block and its files |
| [`add-test`](testing.md#add-test) | Testing | Generate a test for a block that has none |
| [`newbench`](testing.md#newbench) | Benchmarking | Generate a throughput benchmark |
| [`test`](testing.md#test) | Testing | Run one block's test without rebuilding |
| [`init`](project.md#init) | Project health | Adopt an existing project |
| [`check`](project.md#check) | Project health | Audit for out-of-sync state |
| [`info`](project.md#info) | Project health | List groups and blocks |
| [`show`](project.md#show) | Project health | Display a block's source |
| [`build`](building.md#build) | Building | Configure and build |
| [`format`](building.md#format) | Building | Run clang-format |
| [`tui`](tui.md) | Interactive | Terminal UI |
