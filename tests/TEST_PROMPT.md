# nvim-mcp Comprehensive Tool Test

You are testing every tool in the nvim-mcp MCP server. Run each section
in order. After every action, call `get_state` to verify the result.
Do NOT wait for user input between steps — run everything autonomously
and produce a final report.

## Setup

1. Connect to Neovim with `connect`.
2. Call `get_state` and record the initial cwd.
3. Use `send_command` to open the first fixture file:
   `e tests/fixtures/calculator.py`
4. Verify via `get_state`:
   - mode is "normal"
   - one window, buftype "file", filetype "python"
   - file path ends with `tests/fixtures/calculator.py`
   - total_lines is 41

## 1 — State & Navigation

### 1.1 Buffer list

- Call `get_state`. Verify `buffers` contains `calculator.py`.

### 1.2 Open more buffers

- `send_command("e tests/fixtures/broken.py")`
- `send_command("e tests/fixtures/notes.md")`
- Call `get_state`. Verify `buffers` contains all three fixture files.
- Verify the active window shows `notes.md` (the last opened).

### 1.3 Switch active buffer

- `send_command("b calculator.py")`
- Call `get_state`. Verify the active window now shows `calculator.py`.
- Verify `notes.md` is still in `buffers` but not the active window.

### 1.4 Alternate buffer

- Call `get_state`. The window for `calculator.py` should have
  `role: "active"`. If there was a previous window, check for
  `role: "alternate"`.

### 1.5 Relative vs absolute paths

- `send_command("e /etc/hosts")`
- Call `get_state`. Verify that `calculator.py` appears as a relative
  path in `buffers`, while `/etc/hosts` appears as an absolute path
  (since it's outside cwd).
- `send_command("bd /etc/hosts")` — close it.

## 2 — Reading Buffers

### 2.1 Read full buffer

- `read_full_buf("tests/fixtures/calculator.py")`
- Verify the output contains all 41 lines.
- Verify line 1 contains `"""A simple calculator module`.
- Verify line 5 contains `return a + b`.
- Verify line 41 contains `return OPERATIONS[op](a, b)`.

### 2.2 Read buffer range

- `read_buf_range("tests/fixtures/calculator.py", 4, 6)`
- Verify exactly 3 lines returned.
- Verify the range covers the `add` function.

### 2.3 Read a non-active buffer

- `read_full_buf("tests/fixtures/notes.md")`
- Verify it returns the markdown content (not an error).
- Verify line 1 is `# Test Notes`.

### 2.4 Read single line

- `read_buf_range("tests/fixtures/calculator.py", 1, 1)`
- Verify exactly 1 line returned: the module docstring.

### 2.5 Read last line

- `read_buf_range("tests/fixtures/calculator.py", 41, 41)`
- Verify exactly 1 line returned containing `return OPERATIONS[op](a, b)`.

### 2.6 Read full range equals read full buffer

- `read_buf_range("tests/fixtures/calculator.py", 1, 41)`
- `read_full_buf("tests/fixtures/calculator.py")`
- Verify both return identical content.

### 2.7 Read buffer not open in Neovim

- `read_full_buf("tests/fixtures/nonexistent.py")`
- Verify an error is returned (file not in any buffer).

## 3 — Writing Buffers

### 3.1 Write full buffer (overwrite)

- `read_full_buf("tests/fixtures/notes.md")` — save the original content.
- `write_full_buf("tests/fixtures/notes.md", "# Replaced\n\nThis is new content.\n")`
- `read_full_buf("tests/fixtures/notes.md")` — verify it now has 3 lines
  and starts with `# Replaced`.
- Call `get_state`. Verify `notes.md` is in `modified_buffers`.

### 3.2 Verify in-memory vs disk divergence

- The buffer is modified in-memory but NOT saved to disk.
- Read `tests/fixtures/notes.md` from disk (not via buffer tools) to
  confirm the disk content still has the original `# Test Notes`.

### 3.3 Undo the overwrite

- Make `notes.md` the active buffer: `send_command("b notes.md")`
- `send_keys("u")` — undo.
- `read_full_buf("tests/fixtures/notes.md")` — verify original content
  is restored (line 1 is `# Test Notes`).
- Call `get_state`. Verify `notes.md` is no longer in `modified_buffers`
  (or is back to its saved state).

### 3.4 Write and save, then verify modified state

- `write_full_buf("tests/fixtures/notes.md", "# Temporary\n\nWill be saved.\n")`
- Call `get_state`. Verify `notes.md` is in `modified_buffers`.
- `send_command("b notes.md")`
- `send_command("w")` — save to disk.
- Call `get_state`. Verify `notes.md` is NOT in `modified_buffers`.
- Read `tests/fixtures/notes.md` from disk to confirm disk content is
  now `# Temporary`.
- Restore: `send_keys("u")` then `send_command("w")` to write the
  original content back.
- Verify disk content is restored to `# Test Notes`.

### 3.5 Write to a new (non-open) buffer

- `write_full_buf("tests/fixtures/scratch.py", "# scratch\nprint('hello')\n")`
- `read_full_buf("tests/fixtures/scratch.py")` — verify content was set.
- Call `get_state`. Verify `scratch.py` appears in `buffers`.
- Clean up: `send_command("bd! tests/fixtures/scratch.py")`

### 3.6 Write empty content

- `write_full_buf("tests/fixtures/notes.md", "")`
- `read_full_buf("tests/fixtures/notes.md")` — verify the buffer is
  empty (0 or 1 lines).
- Undo: `send_command("b notes.md")`, `send_keys("u")`
- `read_full_buf("tests/fixtures/notes.md")` — verify restored.

## 4 — Find and Replace

### 4.1 Basic find and replace

- `find_and_replace_buf("tests/fixtures/calculator.py", "def add(a: int, b: int) -> int:\n    return a + b", "def add(a: int, b: int) -> int:\n    \"\"\"Add two numbers.\"\"\"\n    return a + b")`
- `read_buf_range("tests/fixtures/calculator.py", 4, 7)` — verify the
  docstring was inserted.
- Call `get_state`. Verify `calculator.py` is in `modified_buffers`.

### 4.2 Undo the edit

- Make `calculator.py` active: `send_command("b calculator.py")`
- `send_keys("u")` — undo.
- `read_buf_range("tests/fixtures/calculator.py", 4, 6)` — verify
  the docstring is gone, original content restored.

### 4.3 Find and replace — string not found

- `find_and_replace_buf("tests/fixtures/calculator.py", "this string does not exist anywhere", "replacement")`
- Verify an error is returned indicating no match.

### 4.4 Find and replace — multiple matches

- `find_and_replace_buf("tests/fixtures/calculator.py", "return a", "return a")`
- Verify an error is returned indicating more than one match (the
  string `return a` appears in add, subtract, modulo, and power).

### 4.5 Find and replace on a non-open buffer

- `send_command("bd tests/fixtures/notes.md")` — close notes.md.
- Call `get_state`. Verify `notes.md` is NOT in `buffers`.
- `find_and_replace_buf("tests/fixtures/notes.md", "## Section Two", "## Section 2")`
- `read_full_buf("tests/fixtures/notes.md")` — verify the buffer was
  created and the edit applied.
- Undo: `send_command("b notes.md")`, `send_keys("u")`

## 5 — Windows & Splits

### 5.1 Vertical split

- `send_command("vsplit tests/fixtures/broken.py")`
- Call `get_state`. Verify 2 windows.
- One window shows `broken.py` (active), the other `calculator.py`.

### 5.2 Horizontal split

- `send_command("split tests/fixtures/notes.md")`
- Call `get_state`. Verify 3 windows.
- Active window shows `notes.md`.

### 5.3 Switch between windows

- `send_command("wincmd l")` — move to the right window.
- Call `get_state`. Verify the active window changed.

### 5.4 Close splits

- `send_command("only")` — close all but current window.
- Call `get_state`. Verify 1 window remains.

## 6 — Tabs

### 6.1 Create a new tab

- `send_command("tabnew tests/fixtures/notes.md")`
- Call `get_state`. Verify `tab_count` is 2, `current_tab` is 2.

### 6.2 Switch tabs

- `send_command("tabprev")`
- Call `get_state`. Verify `current_tab` is 1.

### 6.3 Close the extra tab

- `send_command("tablast | tabclose")`
- Call `get_state`. Verify `tab_count` is 1.

## 7 — Modes

### 7.1 Insert mode

- `send_keys("i")`
- Call `get_state`. Verify mode is "insert".
- `send_keys("\x1b")` — Escape back to normal.
- Call `get_state`. Verify mode is "normal".

### 7.2 Visual line mode

- `send_keys("ggVG")`
- Call `get_state`. Verify mode is "visual_line".
- Verify `selection` is present on the active window with
  `start_line: 1`.
- `send_keys("\x1b")` — Escape.
- Call `get_state`. Verify mode is "normal", no selection.

### 7.3 Visual charwise mode

- `send_keys("ggvw")`
- Call `get_state`. Verify mode is "visual".
- Verify `selection` is present with `start_col` and `end_col` values.
- `send_keys("\x1b")` — Escape.

### 7.4 Visual block mode

- `send_keys("gg\x16jj")` — ctrl-v then move down 2 lines.
- Call `get_state`. Verify mode is "visual_block".
- Verify `selection` is present.
- `send_keys("\x1b")` — Escape.

### 7.5 Replace mode

- `send_keys("R")`
- Call `get_state`. Verify mode is "replace".
- `send_keys("\x1b")` — Escape.

### 7.6 Command mode

- `send_keys(":")` — enter command-line mode.
- Call `get_state`. Verify mode is "command".
- `send_keys("\x1b")` — Escape.

### 7.7 send_keys Esc prepend behavior

- `send_keys` auto-prepends Esc. Verify this by entering insert mode
  via `send_command("startinsert")`, then calling `send_keys("iHello")`
  — the Esc should exit insert mode first, then `i` re-enters it and
  types "Hello" would not work as expected. Instead:
- `send_command("startinsert")`
- Call `get_state`. Verify mode is "insert".
- `send_keys("dd")` — Esc is prepended, so this should exit insert
  and delete a line in normal mode.
- Call `get_state`. Verify mode is "normal".
- `send_keys("u")` — undo the delete.

## 8 — Diagnostics

### 8.1 Buffer diagnostics

- `send_command("e tests/fixtures/broken.py")`
- Wait briefly for LSP to attach (call `get_state` and check
  `diagnostics_summary` on the active window — retry a few times if
  needed, LSP may take a moment).
- `get_buf_diagnostics("tests/fixtures/broken.py")`
- Verify at least one diagnostic is returned (type errors or unused
  import).

### 8.2 All diagnostics

- `get_all_diagnostics()`
- Verify it returns diagnostics from `broken.py`.
- Verify it does NOT return diagnostics for `calculator.py` (which
  should be clean).

### 8.3 Diagnostics summary in state

- Call `get_state`. Verify the active window (`broken.py`) has a
  `diagnostics_summary` with at least one non-zero count.

## 9 — Highlights

### 9.1 Single highlight

- `highlight_range("tests/fixtures/calculator.py", 4, 6, "#5f3a3a")`
- Make `calculator.py` visible: `send_command("b calculator.py")`
- Call `get_state`. Verify `mcp_highlights` contains a range covering
  lines 4–6 with color `#5f3a3a`.

### 9.2 Multiple highlights (single file)

- `highlight_ranges([{"file": "tests/fixtures/calculator.py", "start_line": 9, "end_line": 11, "color": "#3a5f3a"}, {"file": "tests/fixtures/calculator.py", "start_line": 14, "end_line": 16, "color": "#2e4a6e"}])`
- Call `get_state`. Verify `mcp_highlights` now has 3 highlight ranges
  (the one from 9.1 plus these two).

### 9.3 Multiple highlights (across files)

- `highlight_ranges([{"file": "tests/fixtures/notes.md", "start_line": 1, "end_line": 3, "color": "#6b5a2a"}, {"file": "tests/fixtures/broken.py", "start_line": 5, "end_line": 6, "color": "#4a3a5f"}])`
- `send_command("b notes.md")`
- Call `get_state`. Verify `mcp_highlights` on the `notes.md` window.

### 9.4 Highlights persist after buffer switch

- `send_command("b broken.py")`
- `send_command("b calculator.py")`
- Call `get_state`. Verify `mcp_highlights` on `calculator.py` still
  has the 3 ranges from 9.1 and 9.2.

### 9.5 Clear highlights (single file)

- `clear_highlights("tests/fixtures/calculator.py")`
- Call `get_state`. Verify `mcp_highlights` is absent or empty for
  `calculator.py`.
- `send_command("b notes.md")`
- Call `get_state`. Verify `mcp_highlights` on `notes.md` still exists
  (clearing one file doesn't affect another).

### 9.6 Clear remaining highlights

- `clear_highlights("tests/fixtures/notes.md")`
- `clear_highlights("tests/fixtures/broken.py")`

### 9.7 Highlight with default color

- `highlight_range("tests/fixtures/calculator.py", 1, 3)`
- `send_command("b calculator.py")`
- Call `get_state`. Verify `mcp_highlights` exists with the default
  color `#3b4048`.
- `clear_highlights("tests/fixtures/calculator.py")`

## 10 — Terminal

### 10.1 Open a terminal

- `send_command("terminal")`
- Call `get_state`. Verify the active window has `buftype: "terminal"`.
- Verify mode is "normal" or "terminal".

### 10.2 Switch away from terminal

- `send_command("wincmd p")` or `send_command("b calculator.py")`
- Call `get_state`. Verify active window is back to a file buffer
  with `buftype: "file"`.

### 10.3 Close the terminal

- Close the terminal buffer (use `bd!` with the terminal buffer name
  from `get_state`).
- Call `get_state`. Verify no window has `buftype: "terminal"`.

## 11 — Context, Cursor & Marks

### 11.1 Cursor position

- `send_command("b calculator.py")`
- `send_keys("17G5|")` — go to line 17, column 5.
- Call `get_state`. Verify active window has `line: 17`, `col: 5`.

### 11.2 Context lines

- Call `get_state`. Verify `context` on the active window is an array
  of strings containing lines around line 17 with line number prefixes
  (e.g. `"17: ..."`, `"16: ..."`, `"18: ..."`).

### 11.3 Context around visual selection

- `send_keys("5GV10G")` — visual line select lines 5–10.
- Call `get_state`. Verify `context` includes lines around the
  selection range (before line 5 and after line 10).
- `send_keys("\x1b")` — Escape.

### 11.4 Folds

- `send_keys("ggVGzf")` — select all and fold.
- Call `get_state`. Verify `folds` contains at least one range.
- `send_keys("zR")` — open all folds.
- Call `get_state`. Verify `folds` is absent or empty.

### 11.5 Set and verify marks

- `send_keys("10Gma")` — go to line 10, set mark `a`.
- `send_keys("20Gmb")` — go to line 20, set mark `b`.
- Call `get_state`. Verify `marks` on the active window contains
  entries for mark `a` (line 10) and mark `b` (line 20).

### 11.6 Indent settings differ between filetypes

- `send_command("b calculator.py")`
- Call `get_state`. Record `indent` for the `calculator.py` window.
- `send_command("b notes.md")`
- Call `get_state`. Record `indent` for the `notes.md` window.
- Note: these may or may not differ depending on Neovim config, but
  verify the `indent` field is present and well-formed on both.

## 12 — send_command with list

### 12.1 Multiple commands in one call

- `send_command(["e tests/fixtures/calculator.py", "vsplit tests/fixtures/notes.md"])`
- Call `get_state`. Verify 2 windows: one showing `calculator.py`, one
  showing `notes.md`.
- `send_command("only")`

### 12.2 List return value

- The return value of `send_command` with a list should itself be a
  list of results (one per command). Verify the return has 2 entries.

## 13 — Error Handling

### 13.1 Invalid ex command

- `send_command("thiscommanddoesnotexist")`
- Verify an error is returned (not a crash).

### 13.2 Read range beyond end of file

- `read_buf_range("tests/fixtures/calculator.py", 100, 200)`
- Verify either an error or an empty result (not a crash).

### 13.3 Highlight on non-open buffer

- `send_command("bd tests/fixtures/broken.py")`
- `highlight_range("tests/fixtures/broken.py", 1, 5, "#5f3a3a")`
- Verify either an error or graceful handling.
- Re-open: `send_command("e tests/fixtures/broken.py")`

## 14 — Empty Buffer

### 14.1 New empty buffer

- `send_command("enew")`
- Call `get_state`. Verify the active window has total_lines of 1
  (Neovim always has at least one line), buftype "file", and the file
  path is empty.
- `read_full_buf` on the current buffer — verify it returns the empty
  (or single empty line) content.
- `send_command("bd")`

## 15 — Multi-file Edit Workflow

This tests a realistic developer workflow end-to-end.

1. Open `calculator.py` in a split with `notes.md`:
   `send_command("e tests/fixtures/calculator.py | vsplit tests/fixtures/notes.md")`
2. Call `get_state`. Verify 2 windows, both buftype "file".
3. Add a docstring to `divide` in `calculator.py`:
   `find_and_replace_buf("tests/fixtures/calculator.py", "def divide(a: int, b: int) -> float:\n    return a / b", "def divide(a: int, b: int) -> float:\n    \"\"\"Divide a by b. Raises ZeroDivisionError if b is 0.\"\"\"\n    return a / b")`
4. Read back the range to verify:
   `read_buf_range("tests/fixtures/calculator.py", 16, 19)`
5. Add a new section to `notes.md`:
   `find_and_replace_buf("tests/fixtures/notes.md", "## Section Three", "## Section 2.5\n\nAdded during testing.\n\n## Section Three")`
6. Read back to verify:
   `read_full_buf("tests/fixtures/notes.md")`
7. Call `get_state`. Verify both files are in `modified_buffers`.
8. Highlight the edited regions:
   `highlight_ranges([{"file": "tests/fixtures/calculator.py", "start_line": 16, "end_line": 18, "color": "#3a5f3a"}, {"file": "tests/fixtures/notes.md", "start_line": 15, "end_line": 18, "color": "#3a5f3a"}])`
9. Verify highlights on both windows via `get_state`.
10. Clear all highlights:
    `clear_highlights("tests/fixtures/calculator.py")`
    `clear_highlights("tests/fixtures/notes.md")`
11. Undo both edits:
    - `send_command("b calculator.py")`, `send_keys("u")`
    - `send_command("b notes.md")`, `send_keys("u")`
12. Call `get_state`. Verify `modified_buffers` is empty.

## Cleanup

1. Close all splits: `send_command("only")`
2. Close all buffers except the current:
   `send_command("%bd | e# | bd#")`
3. Call `get_state`. Verify 1 window, 1 tab, mode "normal".

## Report

Print a summary table of every check with PASS or FAIL:

```
Section | Check                                    | Result
--------|------------------------------------------|---------
Setup   | connect succeeds                         | PASS
Setup   | calculator.py has 41 lines               | PASS
1.2     | all 3 fixtures in buffers                | PASS
1.5     | relative path for in-cwd file            | PASS
1.5     | absolute path for out-of-cwd file        | PASS
2.4     | single line read returns 1 line           | PASS
2.7     | read non-open buffer returns error        | PASS
3.4     | modified_buffers empty after save         | PASS
4.3     | no-match returns error                   | PASS
4.4     | multiple-match returns error              | PASS
7.3     | charwise visual mode detected             | PASS
7.4     | visual block mode detected                | PASS
9.3     | cross-file highlights applied             | PASS
9.5     | clear one file doesn't affect another     | PASS
11.5    | marks a and b at correct lines            | PASS
12.1    | command list opens split                  | PASS
13.1    | invalid command returns error             | PASS
...
```

If any check failed, include the expected vs actual values.
