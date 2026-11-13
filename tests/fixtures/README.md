Frozen copies of team files for the tests. Tests must load teams from here, never from `teams/`:
the user edits those and the build page saves over them. To use a new team in a test, copy its
committed version here (`git show HEAD:teams/<name>.yaml > tests/fixtures/<name>.yaml`).
