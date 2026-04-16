"""Lua scripts sent to Neovim via exec_lua for state, diagnostics, editing, and highlights.

Public API: GET_STATE, GET_DIAGNOSTICS, EDIT_BUF, READ_BUF, HIGHLIGHT, EXEC_COMMAND.
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
# highlights, marks), buffer list, and tab info.
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
    + _COLLECT_MARKS
    + _COLLECT_LISTED_BUFFERS
)

GET_STATE = _GET_STATE_HELPERS + """\
local active_n = select(1, ...) or 20
local inactive_n = select(2, ...) or active_n
local cur_win = vim.api.nvim_get_current_win()
local alt_win = vim.fn.win_getid(vim.fn.winnr('#'))
local raw_mode = vim.fn.mode()
local mode_names = {
    n = "normal", i = "insert", v = "visual", V = "visual_line",
    ["\\22"] = "visual_block", R = "replace", c = "command", t = "terminal",
    s = "select", S = "select_line", ["\\19"] = "select_block",
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
return {
    mode = cur_mode,
    cwd = cwd,
    modified_buffers = modified,
    buffers = buffers,
    current_tab = vim.fn.tabpagenr(),
    tab_count = vim.fn.tabpagenr('$'),
    windows = wins,
}
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

local group = "McpHl_" .. color:gsub("[^%w]", "_")
vim.api.nvim_set_hl(0, group, {bg = color})

for line = sl, el do
    vim.api.nvim_buf_set_extmark(b, ns, line - 1, 0, {
        line_hl_group = group,
    })
end
return {highlighted = el - sl + 1}
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
