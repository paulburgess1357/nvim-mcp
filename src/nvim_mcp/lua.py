"""Lua scripts sent to Neovim via exec_lua for state, diagnostics, editing, highlights, and virtual text.

Public API: GET_STATE, GET_STATE_BRIEF, GET_DIAGNOSTICS, EDIT_BUF, READ_BUF, HIGHLIGHT, VIRTUAL_TEXT, EXEC_COMMAND, SEND_TO_TERMINAL.
Long scripts are composed from private helper snippets (_SEV_NAMES, _REL_PATH, etc.)
to keep each piece focused and eliminate duplication.
"""

# ---------------------------------------------------------------------------
# Shared Lua helpers — reusable across multiple scripts
# ---------------------------------------------------------------------------

# ---- _SEV_NAMES -----------------------------------------------------------
# Severity lookup table used by GET_STATE (diag summary) and GET_DIAGNOSTICS.
_SEV_NAMES = 'local sev_names = {"error", "warning", "info", "hint"}\n'

# ---- _REL_PATH ------------------------------------------------------------
# Resolve absolute paths to cwd-relative paths.
_REL_PATH = """\
local cwd = vim.fn.getcwd()
local cwd_slash = cwd:sub(-1) == "/" and cwd or (cwd .. "/")
local function rel_path(p)
    if p:sub(1, #cwd_slash) == cwd_slash then
        return p:sub(#cwd_slash + 1)
    end
    return p
end
"""

# ---- _GET_CONTEXT ----------------------------------------------------------
# Return numbered lines surrounding a line range in a buffer.
_GET_CONTEXT = """\
local function get_context(b, from, to, n)
    local total = vim.api.nvim_buf_line_count(b)
    local s = math.max(1, from - n)
    local e = math.min(total, to + n)
    local lines = vim.api.nvim_buf_get_lines(b, s - 1, e, false)
    for i, l in ipairs(lines) do
        lines[i] = (s + i - 1) .. ": " .. l
    end
    return lines
end
"""

# ---------------------------------------------------------------------------
# GET_STATE helpers — per-window data collectors and builders
# ---------------------------------------------------------------------------

# ---- _COLLECT_VISUAL_AND_CONTEXT -------------------------------------------
# Populate selection range (in visual modes) and surrounding context lines.
_COLLECT_VISUAL_AND_CONTEXT = """\
local function collect_visual_and_context(b, winfo, is_active, cur_mode, wline, ctx_n)
    if is_active and (cur_mode == 'visual' or cur_mode == 'visual_line' or cur_mode == 'visual_block') then
        local vpos = vim.fn.getpos('v')
        local cpos = vim.fn.getpos('.')
        local sl, sc = vpos[2], vpos[3]
        local el, ec = cpos[2], cpos[3]
        if sl > el or (sl == el and sc > ec) then
            sl, sc, el, ec = el, ec, sl, sc
        end
        winfo.selection = {
            start_line = sl, start_col = sc,
            end_line = el, end_col = ec,
            mode = cur_mode,
        }
        if ctx_n > 0 then
            winfo.context = get_context(b, sl, el, ctx_n)
        end
    elseif ctx_n > 0 then
        winfo.context = get_context(b, wline, wline, ctx_n)
    end
end
"""

# ---- _COLLECT_FOLDS --------------------------------------------------------
# Scan for closed folds in a window. Returns {start, end} pairs or nil.
_COLLECT_FOLDS = """\
local function collect_folds(w, b)
    local folds = {}
    vim.api.nvim_win_call(w, function()
        local total = vim.api.nvim_buf_line_count(b)
        local ln = 1
        while ln <= total do
            local fc = vim.fn.foldclosed(ln)
            if fc == ln then
                local fe = vim.fn.foldclosedend(ln)
                folds[#folds + 1] = {fc, fe}
                ln = fe + 1
            else
                ln = ln + 1
            end
        end
    end)
    return #folds > 0 and folds or nil
end
"""

# ---- _COLLECT_DIAG_SUMMARY -------------------------------------------------
# Count diagnostics per severity for a buffer. Returns counts or nil.
_COLLECT_DIAG_SUMMARY = """\
local function collect_diag_summary(b)
    local diags = vim.diagnostic.get(b)
    local dcounts = {error = 0, warning = 0, info = 0, hint = 0}
    for _, d in ipairs(diags) do
        local s = sev_names[d.severity] or "hint"
        dcounts[s] = dcounts[s] + 1
    end
    if dcounts.error + dcounts.warning + dcounts.info + dcounts.hint > 0 then
        return dcounts
    end
    return nil
end
"""

# ---- _COLLECT_MCP_HIGHLIGHTS -----------------------------------------------
# Read MCP extmarks and merge adjacent same-color lines into ranges.
_COLLECT_MCP_HIGHLIGHTS = """\
local function collect_mcp_highlights(b)
    local mcp_ns = vim.api.nvim_create_namespace('mcp_highlight')
    local marks = vim.api.nvim_buf_get_extmarks(b, mcp_ns, 0, -1, {details = true})
    if #marks == 0 then return nil end
    local highlights = {}
    for _, m in ipairs(marks) do
        local line = m[2] + 1
        local group = m[4].line_hl_group or ""
        local bg = ""
        if group ~= "" then
            local hl = vim.api.nvim_get_hl(0, {name = group})
            if hl.bg then bg = string.format("#%06x", hl.bg) end
        end
        local prev = highlights[#highlights]
        if prev and prev.color == bg and prev.end_line == line - 1 then
            prev.end_line = line
        else
            highlights[#highlights + 1] = {start_line = line, end_line = line, color = bg}
        end
    end
    return highlights
end
"""

# ---- _COLLECT_MCP_VIRTUAL_TEXT ---------------------------------------------
# Read MCP virtual text extmarks and emit one entry per extmark.
_COLLECT_MCP_VIRTUAL_TEXT = """\
local function collect_mcp_virtual_text(b)
    local mcp_ns = vim.api.nvim_create_namespace('mcp_virtual_text')
    local marks = vim.api.nvim_buf_get_extmarks(b, mcp_ns, 0, -1, {details = true})
    if #marks == 0 then return nil end
    local items = {}
    for _, m in ipairs(marks) do
        local line = m[2] + 1
        local d = m[4]
        local position, lines, color
        if d.virt_text then
            position = "eol"
            lines = { d.virt_text[1][1] }
            color = d.virt_text[1][2] or ""
        elseif d.virt_lines then
            position = d.virt_lines_above and "above" or "below"
            lines = {}
            for _, chunk_list in ipairs(d.virt_lines) do
                lines[#lines + 1] = chunk_list[1][1]
            end
            local first = d.virt_lines[1] and d.virt_lines[1][1]
            color = (first and first[2]) or ""
        end
        if position then
            items[#items + 1] = {
                line = line, position = position,
                lines = lines, color = color,
            }
        end
    end
    return items
end
"""

# ---- _COLLECT_MARKS --------------------------------------------------------
# Collect lowercase buffer marks (a-z) with positions.
_COLLECT_MARKS = """\
local function collect_marks(b)
    local buf_marks = {}
    for c = string.byte('a'), string.byte('z') do
        local mark = vim.api.nvim_buf_get_mark(b, string.char(c))
        if mark[1] > 0 then
            buf_marks[#buf_marks + 1] = {mark = string.char(c), line = mark[1], col = mark[2] + 1}
        end
    end
    return #buf_marks > 0 and buf_marks or nil
end
"""

# ---- _COLLECT_TERMINALS ----------------------------------------------------
# Gather all loaded terminal buffers: buffer number, name, visibility.
# Used by the state snapshots and by SEND_TO_TERMINAL. Requires _REL_PATH.
_COLLECT_TERMINALS = """\
local function collect_terminals()
    local terms = {}
    for _, b in ipairs(vim.api.nvim_list_bufs()) do
        if vim.api.nvim_buf_is_loaded(b) and vim.bo[b].buftype == "terminal" then
            terms[#terms + 1] = {
                buf = b,
                name = rel_path(vim.api.nvim_buf_get_name(b)),
                visible = vim.fn.bufwinid(b) ~= -1,
            }
        end
    end
    return terms
end
"""

# ---- _BUILD_WINDOW_INFO ----------------------------------------------------
# Build the metadata table for a single window (file, cursor, indent, etc.).
_BUILD_WINDOW_INFO = """\
local function build_window_info(w, b, is_active, alt_win)
    local cursor = vim.api.nvim_win_get_cursor(w)
    local raw_bt = vim.bo[b].buftype
    return {
        file = rel_path(vim.api.nvim_buf_get_name(b)),
        filetype = vim.bo[b].filetype,
        total_lines = vim.api.nvim_buf_line_count(b),
        modified = vim.bo[b].modified,
        buftype = raw_bt == "" and "file" or raw_bt,
        role = is_active and "active" or (w == alt_win and "alternate" or nil),
        line = cursor[1],
        col = cursor[2] + 1,
        indent = {
            expandtab = vim.bo[b].expandtab,
            shiftwidth = vim.bo[b].shiftwidth,
            tabstop = vim.bo[b].tabstop,
        },
    }
end
"""

# ---- _COLLECT_LISTED_BUFFERS -----------------------------------------------
# Gather all listed/loaded buffer paths and which ones are modified.
_COLLECT_LISTED_BUFFERS = """\
local function collect_listed_buffers()
    local modified = {}
    local buffers = {}
    for _, b in ipairs(vim.api.nvim_list_bufs()) do
        if vim.bo[b].buflisted and vim.api.nvim_buf_is_loaded(b) then
            local name = vim.api.nvim_buf_get_name(b)
            if name ~= "" then
                local rp = rel_path(name)
                buffers[#buffers + 1] = rp
                if vim.bo[b].modified then
                    modified[#modified + 1] = rp
                end
            end
        end
    end
    return buffers, modified
end
"""

# ---------------------------------------------------------------------------
# EDIT_BUF helpers — buffer acquisition and find-and-replace logic
# ---------------------------------------------------------------------------

# ---- _FIND_OR_CREATE_BUF ---------------------------------------------------
# Look up a buffer by path, creating and loading it if it doesn't exist.
_FIND_OR_CREATE_BUF = """\
local function find_or_create_buf(file)
    local b = vim.fn.bufnr(file)
    if b == -1 then
        b = vim.fn.bufadd(file)
        vim.fn.bufload(b)
        vim.bo[b].buflisted = true
    end
    if not vim.api.nvim_buf_is_loaded(b) then
        vim.fn.bufload(b)
    end
    return b
end
"""

# ---- _FIND_AND_REPLACE -----------------------------------------------------
# Locate a unique occurrence of old_str in the buffer and splice in new_str.
_FIND_AND_REPLACE = """\
local function find_and_replace(b, old_str, new_str)
    local lines = vim.api.nvim_buf_get_lines(b, 0, -1, false)
    local text = table.concat(lines, "\\n")
    local s, e = string.find(text, old_str, 1, true)
    if not s then
        return {error = "old_string not found in buffer"}
    end
    if string.find(text, old_str, e + 1, true) then
        return {error = "old_string matches multiple locations; add context to make it unique"}
    end
    local before = text:sub(1, s - 1)
    local start_line = select(2, before:gsub("\\n", ""))
    local end_line = start_line + select(2, old_str:gsub("\\n", ""))
    local prefix = before:match("[^\\n]*$") or ""
    local suffix = (text:sub(e + 1)):match("^[^\\n]*") or ""
    local replacement = prefix .. new_str .. suffix
    local new_lines = vim.split(replacement, "\\n", {plain = true})
    vim.api.nvim_buf_set_lines(b, start_line, end_line + 1, false, new_lines)
    return {
        start_line = start_line + 1,
        lines_removed = end_line - start_line + 1,
        lines_added = #new_lines,
        total_lines = vim.api.nvim_buf_line_count(b),
    }
end
"""

# ---------------------------------------------------------------------------
# Public Lua scripts — the API consumed by manager.py
# ---------------------------------------------------------------------------

# ---- GET_STATE ------------------------------------------------------------
# Full editor snapshot: mode, windows (with context, folds, diagnostics,
# highlights, marks), buffer list, terminal list, and tab info.
# Args: active_context_lines, inactive_context_lines

_GET_STATE_HELPERS = (
    _REL_PATH
    + _GET_CONTEXT
    + _SEV_NAMES
    + _BUILD_WINDOW_INFO
    + _COLLECT_VISUAL_AND_CONTEXT
    + _COLLECT_FOLDS
    + _COLLECT_DIAG_SUMMARY
    + _COLLECT_MCP_HIGHLIGHTS
    + _COLLECT_MCP_VIRTUAL_TEXT
    + _COLLECT_MARKS
    + _COLLECT_LISTED_BUFFERS
    + _COLLECT_TERMINALS
)

GET_STATE = _GET_STATE_HELPERS + """\
local active_n = select(1, ...) or 20
local inactive_n = select(2, ...) or active_n
local cur_win = vim.api.nvim_get_current_win()
local alt_win = vim.fn.win_getid(vim.fn.winnr('#'))
local raw_mode = vim.fn.mode()
local mode_names = {
    n = "normal", i = "insert", v = "visual", V = "visual_line",
    ["\\22"] = "visual_block", R = "replace", Rv = "vreplace",
    c = "command", t = "terminal",
    s = "select", S = "select_line", ["\\19"] = "select_block",
    no = "operator_pending", nov = "operator_pending",
    noV = "operator_pending", ["no\\22"] = "operator_pending",
    r = "prompt", rm = "prompt", ["r?"] = "prompt",
}
local cur_mode = mode_names[raw_mode] or raw_mode

local wins = {}
for _, w in ipairs(vim.api.nvim_tabpage_list_wins(0)) do
    local b = vim.api.nvim_win_get_buf(w)
    local is_active = (w == cur_win)
    local winfo = build_window_info(w, b, is_active, alt_win)
    local ctx_n = is_active and active_n or inactive_n
    collect_visual_and_context(b, winfo, is_active, cur_mode, winfo.line, ctx_n)
    winfo.folds = collect_folds(w, b)
    winfo.diagnostics_summary = collect_diag_summary(b)
    winfo.mcp_highlights = collect_mcp_highlights(b)
    winfo.mcp_virtual_text = collect_mcp_virtual_text(b)
    winfo.marks = collect_marks(b)
    if is_active then
        table.insert(wins, 1, winfo)
    elseif w == alt_win then
        local pos = math.min(2, #wins + 1)
        table.insert(wins, pos, winfo)
    else
        wins[#wins + 1] = winfo
    end
end
local buffers, modified = collect_listed_buffers()
local terminals = collect_terminals()
return {
    mode = cur_mode,
    cwd = cwd,
    modified_buffers = modified,
    buffers = buffers,
    current_tab = vim.fn.tabpagenr(),
    tab_count = vim.fn.tabpagenr('$'),
    windows = wins,
    terminals = #terminals > 0 and terminals or nil,
}
"""

# ---- GET_STATE_BRIEF ------------------------------------------------------
# Lightweight editor snapshot: mode, cwd, buffer list, terminal list,
# active window and alternate window (both with context lines). No folds,
# marks, diagnostics, highlights, indent settings, or other windows.
# Args: context_lines (default 5)

GET_STATE_BRIEF = _REL_PATH + _GET_CONTEXT + _COLLECT_LISTED_BUFFERS + _COLLECT_TERMINALS + """\
local ctx_n = select(1, ...) or 5
local cur_win = vim.api.nvim_get_current_win()
local alt_win = vim.fn.win_getid(vim.fn.winnr('#'))
local b = vim.api.nvim_win_get_buf(cur_win)
local cursor = vim.api.nvim_win_get_cursor(cur_win)
local raw_bt = vim.bo[b].buftype
local raw_mode = vim.fn.mode()
local mode_names = {
    n = "normal", i = "insert", v = "visual", V = "visual_line",
    ["\\22"] = "visual_block", R = "replace", Rv = "vreplace",
    c = "command", t = "terminal",
    s = "select", S = "select_line", ["\\19"] = "select_block",
    no = "operator_pending", nov = "operator_pending",
    noV = "operator_pending", ["no\\22"] = "operator_pending",
    r = "prompt", rm = "prompt", ["r?"] = "prompt",
}
local active = {
    file = rel_path(vim.api.nvim_buf_get_name(b)),
    filetype = vim.bo[b].filetype,
    total_lines = vim.api.nvim_buf_line_count(b),
    modified = vim.bo[b].modified,
    buftype = raw_bt == "" and "file" or raw_bt,
    line = cursor[1],
    col = cursor[2] + 1,
}
if ctx_n > 0 then
    active.context = get_context(b, cursor[1], cursor[1], ctx_n)
end
local alternate = nil
if alt_win ~= 0 and alt_win ~= cur_win then
    local ab = vim.api.nvim_win_get_buf(alt_win)
    local ac = vim.api.nvim_win_get_cursor(alt_win)
    local abt = vim.bo[ab].buftype
    alternate = {
        file = rel_path(vim.api.nvim_buf_get_name(ab)),
        filetype = vim.bo[ab].filetype,
        total_lines = vim.api.nvim_buf_line_count(ab),
        modified = vim.bo[ab].modified,
        buftype = abt == "" and "file" or abt,
        line = ac[1],
        col = ac[2] + 1,
    }
    if ctx_n > 0 then
        alternate.context = get_context(ab, ac[1], ac[1], ctx_n)
    end
end
local buffers, modified = collect_listed_buffers()
local result = {
    mode = mode_names[raw_mode] or raw_mode,
    cwd = cwd,
    buffers = buffers,
    modified_buffers = modified,
    active_window = active,
}
if alternate then
    result.alternate_window = alternate
end
local terminals = collect_terminals()
if #terminals > 0 then
    result.terminals = terminals
end
return result
"""

# ---- GET_DIAGNOSTICS ------------------------------------------------------
# Collect LSP diagnostics for a specific file or all loaded buffers.
# Args: file (optional, nil for all buffers)

GET_DIAGNOSTICS = _SEV_NAMES + """\
local file = ...
if type(file) == "userdata" then file = nil end
local bufs = {}
if file then
    local b = vim.fn.bufnr(file)
    if b == -1 then return {error = "Buffer not found: " .. tostring(file)} end
    bufs[1] = b
else
    for _, b in ipairs(vim.api.nvim_list_bufs()) do
        if vim.bo[b].buflisted and vim.api.nvim_buf_is_loaded(b) then
            bufs[#bufs + 1] = b
        end
    end
end
local result = {}
for _, b in ipairs(bufs) do
    local diags = vim.diagnostic.get(b)
    if #diags > 0 then
        local name = vim.api.nvim_buf_get_name(b)
        for _, d in ipairs(diags) do
            result[#result + 1] = {
                file = name,
                line = d.lnum + 1,
                col = d.col + 1,
                severity = sev_names[d.severity] or "hint",
                message = d.message,
                source = d.source or "",
            }
        end
    end
end
return result
"""

# ---- EDIT_BUF -------------------------------------------------------------
# Write or replace buffer content. In write mode (old_str is nil/empty),
# replaces the entire buffer. In replace mode, finds a unique match of
# old_str and splices in new_str. Creates the buffer if it doesn't exist.
# Args: file, old_str, new_str

EDIT_BUF = _FIND_OR_CREATE_BUF + _FIND_AND_REPLACE + """\
local file, old_str, new_str = ...
if type(old_str) == "userdata" then old_str = nil end
local b = find_or_create_buf(file)
if old_str == nil or old_str == "" then
    local new_lines = vim.split(new_str, "\\n", {plain = true})
    vim.api.nvim_buf_set_lines(b, 0, -1, false, new_lines)
    return {total_lines = #new_lines}
end
return find_and_replace(b, old_str, new_str)
"""

# ---- READ_BUF -------------------------------------------------------------
# Read numbered lines from a buffer with optional line range.
# Args: file, start_line (optional), end_line (optional)

READ_BUF = """\
local file, start_line, end_line = ...
local b = vim.fn.bufnr(file)
if b == -1 then return {error = "Buffer not found: " .. tostring(file)} end
local total = vim.api.nvim_buf_line_count(b)
local s = (type(start_line) == "number") and start_line or 1
local e = (type(end_line) == "number") and end_line or total
if s > e then s, e = e, s end
if s < 1 then s = 1 end
if e > total then e = total end
local lines = vim.api.nvim_buf_get_lines(b, s - 1, e, false)
for i, l in ipairs(lines) do
    lines[i] = (s + i - 1) .. ": " .. l
end
return {lines = lines, total_lines = total}
"""

# ---- HIGHLIGHT ------------------------------------------------------------
# Apply or clear line highlights in the 'mcp_highlight' namespace.
# Args: file, start_line, end_line, color, clear

HIGHLIGHT = """\
local file, start_line, end_line, color, clear = ...
if type(start_line) == "userdata" then start_line = nil end
if type(end_line) == "userdata" then end_line = nil end
if type(color) == "userdata" then color = nil end
if type(clear) == "userdata" then clear = nil end

local b = vim.fn.bufnr(file)
if b == -1 then
    return {error = "Buffer not found: " .. tostring(file)}
end

local ns = vim.api.nvim_create_namespace('mcp_highlight')

if clear then
    vim.api.nvim_buf_clear_namespace(b, ns, 0, -1)
    return {cleared = true}
end

if not start_line or not end_line then
    return {error = "start_line and end_line are required (pass clear=true to remove highlights)"}
end
if not color then
    return {error = "color is required when highlighting"}
end

local total = vim.api.nvim_buf_line_count(b)
local sl = start_line
local el = end_line
if sl > el then sl, el = el, sl end
if sl < 1 then sl = 1 end
if el > total then el = total end

-- Color must be either a hex literal (#RRGGBB) or a highlight-group
-- name (e.g. "Comment", "DiagnosticError"). For groups, the resolved
-- fg becomes the line background, which adapts to the colorscheme.
local bg_color
if color:sub(1, 1) == "#" then
    bg_color = color
else
    local ok, hl = pcall(vim.api.nvim_get_hl, 0, {name = color, link = false})
    if not ok or type(hl) ~= "table" or next(hl) == nil then
        return {error = "Unknown color: '" .. color .. "'. Use a hex code (e.g. '#RRGGBB') or a highlight group name (e.g. 'Comment', 'DiagnosticError')."}
    end
    local fg = hl.fg or hl.foreground
    local bg = hl.bg or hl.background
    if fg then
        bg_color = string.format("#%06x", fg)
    elseif bg then
        bg_color = string.format("#%06x", bg)
    else
        return {error = "Highlight group '" .. color .. "' has no fg/bg color to use as a line background"}
    end
end

local group = "McpHl_" .. color:gsub("[^%w]", "_")
vim.api.nvim_set_hl(0, group, {bg = bg_color})

for line = sl, el do
    vim.api.nvim_buf_set_extmark(b, ns, line - 1, 0, {
        line_hl_group = group,
    })
end
return {highlighted = el - sl + 1}
"""

# ---- VIRTUAL_TEXT --------------------------------------------------------
# Add or clear virtual text annotations in the 'mcp_virtual_text' namespace.
# Args: file, line, text (list of strings), position ("eol"/"above"/"below"),
#       color (hl-group name or hex), clear (bool)

VIRTUAL_TEXT = """\
local file, line, text, position, color, clear = ...
if type(line) == "userdata" then line = nil end
if type(text) == "userdata" then text = nil end
if type(position) == "userdata" then position = nil end
if type(color) == "userdata" then color = nil end
if type(clear) == "userdata" then clear = nil end

local b = vim.fn.bufnr(file)
if b == -1 then
    return {error = "Buffer not found: " .. tostring(file)}
end

local ns = vim.api.nvim_create_namespace('mcp_virtual_text')

if clear then
    vim.api.nvim_buf_clear_namespace(b, ns, 0, -1)
    return {cleared = true}
end

if not line or not text or not position then
    return {error = "line, text, and position are required (pass clear=true to remove)"}
end

if #text == 0 then
    return {error = "text must be non-empty"}
end

if position ~= "eol" and position ~= "above" and position ~= "below" then
    return {error = "Invalid position: " .. tostring(position) .. ". Must be one of: eol, above, below"}
end

if position == "eol" and #text ~= 1 then
    return {error = "EOL virtual text requires exactly one line"}
end

local total = vim.api.nvim_buf_line_count(b)
local ln = line
if ln < 1 then ln = 1 end
if ln > total then ln = total end

-- Color must be either a hex literal (#RRGGBB) or a highlight-group
-- name (e.g. "Comment", "DiagnosticError"). Hex creates a group whose
-- fg is that color; group names are used directly so they adapt to the
-- colorscheme.
local hl_group
if color:sub(1,1) == "#" then
    hl_group = "McpVt_" .. color:sub(2)
    vim.api.nvim_set_hl(0, hl_group, {fg = color})
else
    local ok, hl = pcall(vim.api.nvim_get_hl, 0, {name = color, link = false})
    if not ok or type(hl) ~= "table" or next(hl) == nil then
        return {error = "Unknown color: '" .. color .. "'. Use a hex code (e.g. '#RRGGBB') or a highlight group name (e.g. 'Comment', 'DiagnosticError')."}
    end
    hl_group = color
end

local opts = {}
if position == "eol" then
    opts.virt_text = {{text[1], hl_group}}
    opts.virt_text_pos = "eol"
else
    local vlines = {}
    for _, t in ipairs(text) do
        vlines[#vlines + 1] = {{t, hl_group}}
    end
    opts.virt_lines = vlines
    if position == "above" then
        opts.virt_lines_above = true
    end
end

vim.api.nvim_buf_set_extmark(b, ns, ln - 1, 0, opts)
return {added = 1}
"""

# ---- SEND_TO_TERMINAL -----------------------------------------------------
# Write text to a terminal buffer's job channel (the running program's
# stdin). Resolves the target by buffer number or name; auto-selects when
# exactly one terminal exists. With submit, appends a carriage return so
# the program executes the input; without, strips trailing newlines so the
# text sits unexecuted at the prompt.
# Args: terminal (number | string | nil), text, submit (bool)

SEND_TO_TERMINAL = _REL_PATH + _COLLECT_TERMINALS + """\
local terminal, text, submit = ...
if type(terminal) == "userdata" then terminal = nil end
if type(submit) == "userdata" then submit = nil end

local terms = collect_terminals()
if #terms == 0 then
    return {error = "No terminal buffers found"}
end

local target
if terminal == nil then
    if #terms == 1 then
        target = terms[1]
    else
        return {
            error = "Multiple terminals found. Specify one with the terminal argument (buffer number or name).",
            terminals = terms,
        }
    end
elseif type(terminal) == "number" then
    for _, t in ipairs(terms) do
        if t.buf == terminal then
            target = t
            break
        end
    end
    if not target then
        return {
            error = "No terminal buffer with number " .. terminal,
            terminals = terms,
        }
    end
else
    local matches = {}
    for _, t in ipairs(terms) do
        if t.name == terminal then
            matches = {t}
            break
        elseif t.name:find(terminal, 1, true) then
            matches[#matches + 1] = t
        end
    end
    if #matches == 1 then
        target = matches[1]
    elseif #matches == 0 then
        return {
            error = "No terminal buffer matching '" .. terminal .. "'",
            terminals = terms,
        }
    else
        return {
            error = "Terminal name '" .. terminal .. "' is ambiguous",
            terminals = matches,
        }
    end
end

local chan = vim.bo[target.buf].channel
if not chan or chan == 0 then
    return {error = "The job in terminal '" .. target.name .. "' has exited"}
end

local payload = text
if submit then
    local last = payload:sub(-1)
    if last ~= "\\n" and last ~= "\\r" then
        payload = payload .. "\\r"
    end
else
    payload = payload:gsub("[\\r\\n]+$", "")
end

-- The channel id can outlive the job (the "[Process exited]" state), so
-- a dead terminal surfaces here as a send error, not as channel == 0.
local ok, err = pcall(vim.api.nvim_chan_send, chan, payload)
if not ok then
    return {error = "Could not send to terminal '" .. target.name .. "': " .. tostring(err)}
end
return {
    sent = #payload,
    terminal = target.name,
    buf = target.buf,
    submitted = submit and true or false,
}
"""

# ---- EXEC_COMMAND ---------------------------------------------------------
# Run a Vim command string and capture output and errors.
# Args: input (command string)

EXEC_COMMAND = """\
local input = ...
vim.v.errmsg = ''
local ok, result = pcall(vim.api.nvim_exec2, input, {output = true})
local output = ok and (result.output or '') or ''
local errmsg = vim.v.errmsg
if not ok then errmsg = tostring(result) end
return {output = output, errmsg = errmsg}
"""
