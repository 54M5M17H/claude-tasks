" Resolve paths at script load time
let s:wiki_path = expand(g:vimwiki_list[0].path)
let s:repo_dir = expand('<sfile>:p:h')

" Function for creating tasks
" <leader>t
" Takes text line and converts it to task with link
" Takes markdown todo and converts it to task with link
" Default folder is todo/ subdir
function! VimwikiTaskToLinkedTask() abort
  let l:line = getline('.')

  " If line already has a wiki link, do nothing
  if l:line =~ '\[\[.\{-}\]\]'
    return
  endif

  " Remove leading task marker (- [ ] / - [X])
  let l:text = substitute(l:line, '^\s*[-*+]\s\+\[[ xX]\]\s\+', '', '')
  " Remove plain list marker (- / * / +)
  let l:text = substitute(l:text, '^\s*[-*+]\s\+', '', '')
  let l:text = trim(l:text)

  if empty(l:text)
    return
  endif

  " Link goes to todo/... but displays without the prefix
  call setline('.', '- [ ] [[todo/' . l:text . '|' . l:text . ']]')
  call cursor(line('.'), strlen(getline('.')) + 1)
endfunction

augroup VimwikiTaskLink
  autocmd!
  autocmd FileType vimwiki nnoremap <buffer> <leader>t :call VimwikiTaskToLinkedTask()<CR>
augroup END


"" Tab for autocomplete, as Vimwiki conflicts with this
au filetype vimwiki silent! iunmap <buffer> <Tab>


" :AITask -- open a new tmux window and run claude with the current vimwiki file as the prompt
function! VimwikiAITask() abort
  let l:filepath = expand('%:p')

  if empty(l:filepath)
    echoerr 'AITask: buffer has no file path'
    return
  endif

  if empty($TMUX)
    echoerr 'AITask: not inside a tmux session'
    return
  endif

  update

  " Move from todo/ to wip/ if currently in todo/
  if l:filepath =~# s:wiki_path . '/todo/'
    VimwikiMv ../wip/
    let l:filepath = expand('%:p')
  endif

  let l:winname = tolower(substitute(expand('%:t:r'), ' ', '-', 'g'))[:20]

  " Create window detached, capture its index
  let l:win_idx = trim(system('tmux new-window -d -n ' . shellescape(l:winname) . ' -e ' . shellescape('AITASK_FILE=' . l:filepath) . ' -PF "#{window_index}"'))
  if v:shell_error
    echoerr 'AITask: failed to create tmux window'
    return
  endif

  " Write the window index to the task file before Claude reads it
  call system('sed -i "" "s/^\*\*Tmux Window\*\*: .*/\*\*Tmux Window\*\*: ' . l:win_idx . '/" ' . shellescape(l:filepath))

  " Start Claude in the window, then switch to it
  call system('tmux send-keys -t :' . l:win_idx . ' ''claude "Read the file $AITASK_FILE for your task instructions. Use $AITASK_FILE as your wip file to report progress updates to."; exec "$SHELL"'' Enter')
  call system('tmux select-window -t :' . l:win_idx)
endfunction

" :VimwikiMv <dest_dir> -- move current wiki file to a different directory
" e.g. :VimwikiMv ../todo/ or :VimwikiMv ../wip/
function! VimwikiMv(dest) abort
  let l:filepath = expand('%:p')
  if empty(l:filepath)
    echoerr 'VimwikiMv: buffer has no file path'
    return
  endif

  update

  let l:taskname = expand('%:t:r')
  let l:target = substitute(a:dest, '/\+$', '', '') . '/' . l:taskname
  execute 'VimwikiRenameFile ' . l:target
endfunction

" :AIManager -- open the task manager dashboard in a new tmux window
function! VimwikiAIManager() abort
  if empty($TMUX)
    echoerr 'AIManager: not inside a tmux session'
    return
  endif

  let l:cmd = 'tmux new-window -n claude-manager -- '
        \ . 'python3 ' . shellescape(s:repo_dir . '/claude_manager.py')
        \ . ' --wiki-path ' . shellescape(s:wiki_path)
  call system(l:cmd)
  if v:shell_error
    echoerr 'AIManager: failed to create tmux window'
  endif
endfunction

augroup VimwikiAITask
  autocmd!
  autocmd FileType vimwiki command! -buffer AITask call VimwikiAITask()
  autocmd FileType vimwiki command! -buffer AIManager call VimwikiAIManager()
  autocmd FileType vimwiki command! -buffer -nargs=1 VimwikiMv call VimwikiMv(<f-args>)
  autocmd FileType vimwiki nnoremap <buffer> <leader>ai :AITask<CR>
  autocmd FileType vimwiki nnoremap <buffer> <leader>mv :VimwikiMv ../
  execute 'autocmd BufNewFile ' . s:wiki_path . '/todo/*.wiki 0r ' . s:repo_dir . '/templates/task.wiki'
augroup END
