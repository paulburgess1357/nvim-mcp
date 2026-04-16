"""Lua scripts sent to Neovim via exec_lua for state, diagnostics, editing, and highlights."""

GET_STATE = """\
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
local cwd = vim.fn.getcwd()
local cwd_slash = cwd:sub(-1) == "/" and cwd or (cwd .. "/")
local function rel_path(p)
    if p:sub(1, #cwd_slash) == cwd_slash then
        return p:sub(#cwd_slash + 1)
    end
    return p
end

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

local wins = {}
for _, w in ipairs(vim.api.nvim_tabpage_list_wins(0)) do
    local b = vim.api.nvim_win_get_buf(w)
    local is_active = (w == cur_win)
    local cursor = vim.api.nvim_win_get_cursor(w)
    local wline, wcol = cursor[1], cursor[2] + 1
    local raw_bt = vim.bo[b].buftype
    local winfo = {
        file = rel_path(vim.api.nvim_buf_get_name(b)),
        filetype = vim.bo[b].filetype,
        total_lines = vim.api.nvim_buf_line_count(b),
        modified = vim.bo[b].modified,
        buftype = raw_bt == "" and "file" or raw_bt,
        role = is_active and "active" or (w == alt_win and "alternate" or nil),
        line = wline,
        col = wcol,
        indent = {
            expandtab = vim.bo[b].expandtab,
            shiftwidth = vim.bo[b].shiftwidth,
            tabstop = vim.bo[b].tabstop,
        },
    }
    local ctx_n = is_active and active_n or inactive_n
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
    if #folds > 0 then
        winfo.folds = folds
    end
    local sev_names = {"error", "warning", "info", "hint"}
    local diags = vim.diagnostic.get(b)
    local dcounts = {error = 0, warning = 0, info = 0, hint = 0}
    for _, d in ipairs(diags) do
        local s = sev_names[d.severity] or "hint"
        dcounts[s] = dcounts[s] + 1
    end
    if dcounts.error + dcounts.warning + dcounts.info + dcounts.hint > 0 then
        winfo.diagnostics_summary = dcounts
    end
    local mcp_ns = vim.api.nvim_create_namespace('mcp_highlight')
    local marks = vim.api.nvim_buf_get_extmarks(b, mcp_ns, 0, -1, {details = true})
    if #marks > 0 then
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
        winfo.mcp_highlights = highlights
    end
    local buf_marks = {}
    for c = string.byte('a'), string.byte('z') do
        local mark = vim.api.nvim_buf_get_mark(b, string.char(c))
        if mark[1] > 0 then
            buf_marks[#buf_marks + 1] = {mark = string.char(c), line = mark[1], col = mark[2] + 1}
        end
    end
    if #buf_marks > 0 then
        winfo.marks = buf_marks
    end
    if is_active then
        table.insert(wins, 1, winfo)
    elseif w == alt_win then
        local pos = math.min(2, #wins + 1)
        table.insert(wins, pos, winfo)
    else
        wins[#wins + 1] = winfo
    end
end
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

GET_DIAGNOSTICS = """\
local file = ...
if file == vim.NIL then file = nil end
local sev_names = {"error", "warning", "info", "hint"}
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

EDIT_BUF = r"""
local file, old_str, new_str = ...

-- Find or create buffer
local b = vim.fn.bufnr(file)
if b == -1 then
    b = vim.fn.bufadd(file)
    vim.fn.bufload(b)
    vim.bo[b].buflisted = true
end
if not vim.api.nvim_buf_is_loaded(b) then
    vim.fn.bufload(b)
end

-- Write mode: no old_str means set entire buffer content
if old_str == nil or old_str == vim.NIL or old_str == "" then
    local new_lines = vim.split(new_str, "\n", {plain = true})
    vim.api.nvim_buf_set_lines(b, 0, -1, false, new_lines)
    return {total_lines = #new_lines}
end

-- Replace mode: find old_str in buffer, replace with new_str
local lines = vim.api.nvim_buf_get_lines(b, 0, -1, false)
local text = table.concat(lines, "\n")

local s, e = string.find(text, old_str, 1, true)
if not s then
    return {error = "old_string not found in buffer"}
end
if string.find(text, old_str, e + 1, true) then
    return {error = "old_string matches multiple locations; add context to make it unique"}
end

-- Compute affected line range (0-indexed)
local before = text:sub(1, s - 1)
local start_line = select(2, before:gsub("\n", ""))
local end_line = start_line + select(2, old_str:gsub("\n", ""))

-- Preserve text on start_line before match and on end_line after match
local prefix = before:match("[^\n]*$") or ""
local suffix = (text:sub(e + 1)):match("^[^\n]*") or ""

local replacement = prefix .. new_str .. suffix
local new_lines = vim.split(replacement, "\n", {plain = true})
vim.api.nvim_buf_set_lines(b, start_line, end_line + 1, false, new_lines)

return {
    start_line = start_line + 1,
    lines_removed = end_line - start_line + 1,
    lines_added = #new_lines,
    total_lines = vim.api.nvim_buf_line_count(b),
}
"""

READ_BUF = """\
local file, start_line, end_line = ...
local b = vim.fn.bufnr(file)
if b == -1 then return {error = "Buffer not found: " .. tostring(file)} end
local total = vim.api.nvim_buf_line_count(b)
local s = (type(start_line) == "number") and start_line or 1
local e = (type(end_line) == "number") and end_line or total
if s < 1 then s = 1 end
if e > total then e = total end
local lines = vim.api.nvim_buf_get_lines(b, s - 1, e, false)
for i, l in ipairs(lines) do
    lines[i] = (s + i - 1) .. ": " .. l
end
return {lines = lines, total_lines = total}
"""

HIGHLIGHT = r"""
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

local total = vim.api.nvim_buf_line_count(b)
local sl = start_line
local el = end_line
color = color or "#3b4048"
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

EXEC_COMMAND = """\
local input = ...
vim.v.errmsg = ''
local ok, result = pcall(vim.api.nvim_exec2, input, {output = true})
local output = ok and (result.output or '') or ''
local errmsg = vim.v.errmsg
if not ok then errmsg = tostring(result) end
return {output = output, errmsg = errmsg}
"""
