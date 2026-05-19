# Tool reference

nvim-mcp exposes the following tools to MCP clients. Agents can also run arbitrary Vim commands and send keystrokes, so these dedicated tools cover the most common operations without requiring the agent to construct raw commands.

## Editor state

| Tool | Description |
| ---- | ----------- |
| `get_state_brief` | Quick snapshot: mode, working directory, listed buffers, active window and alternate window (file, cursor, a few context lines each). Designed for the start of every turn. |
| `get_state` | Full session snapshot: everything in `get_state_brief` plus all window details, folds, visual selections, marks, diagnostics summaries, highlights, and indent settings. |
| `connect` | Discovers running Neovim instances and connects to one. When multiple instances exist, the agent can pick by index, socket path, or terminal PID. |

## Buffers

All buffer edits happen in memory. Nothing is written to disk until the buffer is saved, and every edit is fully undoable.

| Tool | Description |
| ---- | ----------- |
| `read_full_buf` | Read the entire contents of a buffer, with line numbers. |
| `read_buf_range` | Read a specific line range from a buffer. |
| `find_and_replace_buf` | Exact-match find and replace within a buffer. |
| `write_full_buf` | Replace the entire contents of a buffer. |

## Commands and keys

| Tool | Description |
| ---- | ----------- |
| `send_command` | Run one or more ex commands (`:w`, `:e path`, `:wincmd v`, etc.). |
| `send_keys` | Send keystrokes to Neovim. Escape is prepended automatically. |

## Diagnostics

| Tool | Description |
| ---- | ----------- |
| `get_all_diagnostics` | Retrieve LSP diagnostics (errors, warnings, hints) across all buffers. |
| `get_buf_diagnostics` | Retrieve LSP diagnostics for a single buffer. |

## Highlights

Highlights use Neovim extmarks under the `mcp_highlight` namespace.

| Tool | Description |
| ---- | ----------- |
| `highlight_range` | Annotate a line range with a colored highlight. |
| `highlight_ranges` | Annotate multiple ranges at once. |
| `clear_highlights` | Remove all MCP highlights from a buffer. |

## Virtual text

Virtual text uses Neovim extmarks under the `mcp_virtual_text` namespace.
Annotations are visual only — buffer content is unchanged and nothing is
persisted to disk.

| Tool | Description |
| ---- | ----------- |
| `add_virtual_text` | Attach a text annotation to a buffer line (end-of-line, above, or below). |
| `add_virtual_texts` | Attach multiple annotations at once. |
| `clear_virtual_texts` | Remove all MCP virtual text from a buffer. |
