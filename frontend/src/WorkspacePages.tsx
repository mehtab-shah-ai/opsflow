import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ArrowDownToLine, ArrowRight, ChartNoAxesCombined, Check, ChevronRight, CloudUpload, Database, FileSpreadsheet, FileText, Globe2, Link, LoaderCircle, LockKeyhole, RotateCcw, Search, Send, ShieldCheck, Sparkles, Upload, X } from 'lucide-react'
import { api, apiUrl, post } from './api'
import { Badge, ChartPanel, DataTable, display, human, num, Panel } from './components'
import type { ChatMessage, Dataset, Job, Row, Status } from './types'

interface Base {dataset:Dataset;live:boolean;onError:(e:unknown)=>void;onDemo:()=>void}
export function Sources({
  dataset,
  live,
  onError,
  onDemo,
  onFiles,
  onSheet,
  jobs,
  onSelect,
  onOpen,
  onNavigate,
  uploadSuccessNotice,
  onClearUploadNotice,
}: {
  dataset?: Dataset | null
  live: boolean
  onError: (e: unknown) => void
  onDemo: () => void
  onFiles: (f: File[]) => void
  onSheet: (u: string) => void
  jobs: Job[]
  onSelect: (j: Job, t: number) => void
  onOpen: (id: string) => void
  onNavigate?: (p: string) => void
  uploadSuccessNotice?: { filename: string; datasetId?: string; rows?: number } | null
  onClearUploadNotice?: () => void
}) {
  const input = useRef<HTMLInputElement>(null)
  const datasetSectionRef = useRef<HTMLDivElement>(null)
  const [url, setUrl] = useState('')
  const [drag, setDrag] = useState(false)
  const [original, setOriginal] = useState(false)
  const [page, setPage] = useState(1)
  const [sourceTab, setSourceTab] = useState<'file' | 'sheet'>('file')

  const rows = useQuery({
    queryKey: ['rows', dataset?.id, dataset?.version, page, original],
    queryFn: () => (live && dataset?.id)
      ? api<{ items: Row[]; total: number }>(`/api/datasets/${dataset.id}/rows?page=${page}&size=100&original=${original}`)
      : fetch('/demo-rows.json').then(r => r.json()).then(items => ({ items: items as Row[], total: 25 })),
    enabled: !!dataset?.id || !live,
  })

  useEffect(() => {
    setPage(1)
    setOriginal(false)
  }, [dataset?.id])

  // Smoothly scroll down to full "Inside your dataset" section on upload completion
  useEffect(() => {
    if (uploadSuccessNotice) {
      const timer = setTimeout(() => {
        datasetSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }, 120)
      return () => clearTimeout(timer)
    }
  }, [uploadSuccessNotice])

  // Auto-dismiss the "Find with value and Analyze" popup after 5 seconds
  useEffect(() => {
    if (!uploadSuccessNotice) return
    const timer = setTimeout(() => {
      onClearUploadNotice?.()
    }, 5000)
    return () => clearTimeout(timer)
  }, [uploadSuccessNotice, onClearUploadNotice])

  function handleFindWithValue() {
    const searchInp = document.getElementById('dataset-search-input') as HTMLInputElement | null
    if (searchInp) {
      searchInp.focus()
      searchInp.classList.add('search-highlight-pulse')
      setTimeout(() => searchInp.classList.remove('search-highlight-pulse'), 2400)
      searchInp.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }

  return (
    <>
      {/* TOP ROW: Upload on Left & Compact Processing Workspace on Right */}
      <div className="sources-top-grid">
        <Panel className={`sources-upload-panel ${drag ? 'dragging' : ''}`}>
          <div className="sources-upload-tabs">
            <button
              type="button"
              className={`sources-tab-btn ${sourceTab === 'file' ? 'active' : ''}`}
              onClick={() => setSourceTab('file')}
            >
              <Upload size={13} />
              <span>Upload Files (CSV, Excel, PDF)</span>
            </button>
            <button
              type="button"
              className={`sources-tab-btn ${sourceTab === 'sheet' ? 'active' : ''}`}
              onClick={() => setSourceTab('sheet')}
            >
              <Globe2 size={13} />
              <span>Google Sheets</span>
            </button>
          </div>

          {sourceTab === 'file' ? (
            <div
              className="drop-zone compact-dropzone"
              onDragOver={e => { e.preventDefault(); setDrag(true) }}
              onDragLeave={() => setDrag(false)}
              onDrop={e => { e.preventDefault(); setDrag(false); onFiles(Array.from(e.dataTransfer.files)) }}
            >
              <div className="upload-icon compact-icon"><CloudUpload size={24} /></div>
              <h3>Drop operational files to ingest</h3>
              <p className="text-small muted">CSV, Excel (.xlsx, .xls) or PDF · Up to 10 MB per file</p>
              <button type="button" className="button primary small" onClick={() => input.current?.click()}>
                <Upload size={14} />Choose files to upload
              </button>
              <input ref={input} type="file" multiple accept=".csv,.xlsx,.xls,.pdf" hidden onChange={e => { onFiles(Array.from(e.target.files || [])); e.target.value = '' }} />
              <div className="file-types compact-file-types">
                <Badge>CSV</Badge><Badge>Excel</Badge><Badge>PDF</Badge>
                <span className="compact-trust-note"><LockKeyhole size={11} />Raw data preserved</span>
              </div>
            </div>
          ) : (
            <div className="sheet-form compact-sheet-form">
              <label htmlFor="sheet-url">Public Google Sheets URL</label>
              <div className="input-icon">
                <Link size={15} />
                <input id="sheet-url" placeholder="https://docs.google.com/spreadsheets/d/…" value={url} onChange={e => setUrl(e.target.value)} />
              </div>
              <button type="button" className="button secondary full small" onClick={() => onSheet(url)} disabled={!url.trim()}>
                <span>Import worksheet</span><ArrowRight size={14} />
              </button>
              <p className="text-small muted"><Globe2 size={12} />Public link access required. No private credentials needed.</p>
            </div>
          )}
        </Panel>

        {/* RIGHT: Compact Processing Workspace */}
        <Panel
          className="compact-workspace-panel"
          title="Processing workspace"
          subtitle={`${jobs.length} file job${jobs.length === 1 ? '' : 's'}`}
          action={
            <button type="button" className="text-button compact-demo-btn" onClick={onDemo} title="Load synthetic demo">
              <span>Load demo</span><ArrowRight size={12} />
            </button>
          }
        >
          <div className="compact-job-list">
            {jobs.length ? (
              jobs.map(j => {
                const isActive = j.dataset_id === dataset?.id
                return (
                  <div
                    className={`compact-job-row ${isActive ? 'active-job-item' : ''}`}
                    key={j.id}
                    onClick={() => j.dataset_id && onOpen(j.dataset_id)}
                    role="button"
                    tabIndex={0}
                    title={j.dataset_id ? `Click to view ${j.filename} in table` : undefined}
                  >
                    <div className={`compact-file-tile ${j.status === 'failed' ? 'failed' : ''}`}>
                      {j.filename?.toLowerCase().endsWith('.pdf') ? <FileText size={16} /> : <FileSpreadsheet size={16} />}
                    </div>
                    <div className="compact-job-content">
                      <div className="compact-job-title-row">
                        <strong className="compact-filename" title={j.filename}>{j.filename}</strong>
                        <Badge tone={j.status === 'failed' ? 'critical' : j.status === 'completed' ? 'success' : 'warning'}>
                          {human(j.status)}
                        </Badge>
                      </div>
                      <div className="compact-job-meta-row">
                        <span className="compact-job-detail">{j.error || (j.rows ? `${num(j.rows)} rows · ${j.duration}s` : j.stage)}</span>
                        {isActive && <span className="active-pill">Active</span>}
                      </div>
                      {!['completed', 'failed'].includes(j.status) && (
                        <div className="progress-track" style={{ marginTop: '5px' }}>
                          <div style={{ width: j.progress + '%' }} />
                        </div>
                      )}
                      {j.status === 'awaiting_selection' && (
                        <div className="table-choices compact-choices" onClick={e => e.stopPropagation()}>
                          {j.tables?.map(t => (
                            <div key={t.index}>
                              <b>{t.name}</b>
                              <small>{num(t.rows)} rows · {t.columns.length} cols</small>
                              <button type="button" className="button secondary small" onClick={() => onSelect(j, t.index)}>
                                Import<ChevronRight size={12} />
                              </button>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                    {j.dataset_id && (
                      <span className="compact-open-icon" title="View dataset">
                        <ArrowRight size={14} />
                      </span>
                    )}
                  </div>
                )
              })
            ) : (
              <div className="empty compact-empty">
                <FileSpreadsheet size={24} />
                <p>No files processed yet.<br />Drop a file on the left to start.</p>
              </div>
            )}
          </div>
        </Panel>
      </div>

      {/* MAIN: Inside your dataset (Moved UP directly below the top area!) */}
      <div id="dataset-view-section" ref={datasetSectionRef}>
        {dataset ? (
          <Panel
            className="dataset-view-panel"
            title="Inside your dataset"
            subtitle={`${dataset.filename} · ${dataset.table_name}`}
            action={
              <div className="segmented">
                <button className={!original ? 'selected' : ''} onClick={() => setOriginal(false)}>Current version</button>
                <button className={original ? 'selected' : ''} onClick={() => setOriginal(true)}>Original</button>
              </div>
            }
          >
            {/* POP-UP / FLOATING BANNER: "Find with value and Analyze" */}
            {uploadSuccessNotice && (
              <div className="find-analyze-popup-banner">
                <div className="find-analyze-content">
                  <div className="find-analyze-icon">
                    <Sparkles size={20} />
                  </div>
                  <div className="find-analyze-text">
                    <div className="find-analyze-header-row">
                      <span className="find-analyze-badge">Upload Complete</span>
                      <h4>Find with value and Analyze</h4>
                    </div>
                    <p>
                      <strong>{uploadSuccessNotice.filename}</strong> {uploadSuccessNotice.rows ? `(${num(uploadSuccessNotice.rows)} records)` : ''} is ready. Search values directly in the dataset or jump into automated analysis.
                    </p>
                  </div>
                  <div className="find-analyze-actions">
                    <button
                      type="button"
                      className="button lime small find-btn"
                      onClick={handleFindWithValue}
                    >
                      <Search size={13} />
                      <span>Find with value</span>
                    </button>
                    <button
                      type="button"
                      className="button secondary small analyze-btn"
                      onClick={() => onNavigate?.('Analytics')}
                    >
                      <ChartNoAxesCombined size={13} />
                      <span>Analyze</span>
                    </button>
                    <button
                      type="button"
                      className="button secondary small copilot-btn"
                      onClick={() => onNavigate?.('AI Copilot')}
                    >
                      <Sparkles size={13} />
                      <span>AI Copilot</span>
                    </button>
                    <button
                      type="button"
                      className="icon-button close-banner-btn"
                      onClick={onClearUploadNotice}
                      title="Dismiss banner"
                    >
                      <X size={16} />
                    </button>
                  </div>
                </div>
                <div className="popup-countdown-track">
                  <div className="popup-countdown-bar" />
                </div>
              </div>
            )}

            {dataset.warnings.map(w => <p className="inline-notice" key={w}>{w}</p>)}
            {rows.error ? (
              <div className="empty">
                <p>{rows.error.message}</p>
                <button className="button secondary" onClick={() => rows.refetch().catch(onError)}>Retry</button>
              </div>
            ) : (
              <DataTable rows={rows.data?.items || []} highlight={new Set(dataset.analysis.issues.map(i => i.source_row))} />
            )}
            <div className="panel-bottom">
              <span>{live ? `Source page ${page}; up to 100 records loaded at a time` : 'Preview contains 25 sample rows. Load the demo for all records.'}</span>
              {live && (
                <div className="button-row">
                  <button className="text-button" disabled={page === 1} onClick={() => setPage(page - 1)}>Previous source page</button>
                  <button className="text-button" disabled={page * 100 >= (rows.data?.total || 0)} onClick={() => setPage(page + 1)}>Next source page<ArrowRight size={13} /></button>
                </div>
              )}
            </div>
          </Panel>
        ) : (
          <Panel className="dataset-view-panel" title="Inside your dataset" subtitle="Awaiting data file">
            <div className="empty">
              <FileSpreadsheet size={34} />
              <h4>No dataset loaded yet</h4>
              <p>Drop your CSV, Excel (.xlsx, .xls) or PDF above to profile and clean.<br />Your raw originals will remain completely safe and untouched.</p>
              <div className="button-row" style={{ marginTop: '12px' }}>
                <button className="button primary" onClick={() => input.current?.click()}><Upload size={15} />Choose files to upload</button>
                <button className="button secondary" onClick={onDemo}><Sparkles size={15} />Load synthetic demo</button>
              </div>
            </div>
          </Panel>
        )}
      </div>
    </>
  )
}


export function Quality({dataset,live,onClean,onDownload,exceptions=false}:{dataset:Dataset;live:boolean;onClean:()=>void;onDownload:(q:string,n:string)=>void;exceptions?:boolean}) {
 const [severity,setSeverity]=useState('all'),[category,setCategory]=useState('all'),[selected,setSelected]=useState<Row|null>(null)
 const a=dataset.analysis
 const issues=a.issues.filter(i=>(severity==='all'||i.severity===severity)&&(category==='all'||i.issue_type===category))
 const rows=issues.map(i=>({record:i.row,severity:i.severity,field:i.column,finding:human(i.issue_type),current_value:i.current_value,suggested_value:i.suggested_value,reason:i.reason,rule:i.rule,confidence:`${Math.round(i.confidence*100)}%`,action:i.auto_fixable?'Review safe fix':'Manual check needed'}))
 return <><div className="quality-hero"><div><span className="eyebrow">{exceptions?'EXCEPTIONS & ISSUES':'DATA ACCURACY & HEALTH'}</span><h2>{exceptions?'Catch issues before they affect decisions.':'Nothing changes without your approval.'}</h2><p>{exceptions?'Review unusual numbers, staffing gaps, and SLA violations before sharing reports.':'Preview exact old vs new values. All original records are preserved.'}</p></div><ShieldCheck size={60} strokeWidth={1}/></div><div className="quality-stat-grid">{Object.entries(a.severity).map(([s,n])=><button className={`quality-stat ${severity===s?'active':''}`} key={s} onClick={()=>setSeverity(severity===s?'all':s)}><Badge tone={s}>{s==='critical'?'Urgent':s==='warning'?'Review Needed':'Minor / Format'}</Badge><strong>{num(n)}</strong><span>{s==='critical'?'Requires immediate action':s==='warning'?'Double check with original source':'Safe formatting & cleanup'}<ArrowUpRightIcon/></span></button>)}</div>
 {!live&&<div className="inline-notice">Showing a sample of computed demo issues. Load the demo to investigate every record.</div>}
 <Panel title={exceptions?'Issues & Exceptions Register':'Quality & Health Findings'} subtitle="Flagged items highlight potential problems without altering or deleting your data." action={<div className="button-row"><button className="button secondary small" onClick={()=>onDownload(`format=xlsx&kind=issues${severity!=='all'?'&severity='+severity:''}`,'opsflow-exceptions.xlsx')}><ArrowDownToLine size={14}/>Export Excel</button><button className="button primary small" onClick={onClean}><Sparkles size={14}/>Preview & Fix</button></div>}><div className="filters"><div className="segmented">{['all','critical','warning','info'].map(s=><button key={s} className={severity===s?'selected':''} onClick={()=>setSeverity(s)}>{s==='all'?'All Issues':s==='critical'?'Urgent':s==='warning'?'Needs Review':'Minor Cleanups'}</button>)}</div><select aria-label="Issue category" value={category} onChange={e=>setCategory(e.target.value)}><option value="all">All issue categories</option>{Object.keys(a.categories).map(k=><option key={k} value={k}>{human(k)}</option>)}</select></div><DataTable rows={rows} columns={['record','severity','field','finding','current_value','action']} onRow={setSelected}/>{selected&&<div className="row-detail"><button className="text-button" onClick={()=>setSelected(null)}>Close details</button><h4>Row #{display(selected.record)} · Field: {display(selected.field)}</h4><p>{display(selected.reason)}</p><div className="compare-values"><div><small>CURRENT VALUE</small><code>{display(selected.current_value)}</code></div><ArrowRight size={16}/><div><small>SUGGESTED VALUE</small><code>{display(selected.suggested_value)}</code></div></div><p className="muted text-small">Check type: {display(selected.rule)} · Confidence: {display(selected.confidence)}</p></div>}</Panel><Panel title="How the quality score works"><p className="panel-text">Our data quality score gives an honest, objective measure of your dataset's health. It starts at 100% (completely clean and error-free). Urgent issues (like missing required fields or duplicate shifts) deduct the most points, while minor formatting differences have minimal impact. Your original records are never deleted or changed without your explicit approval.</p></Panel></>
}
function ArrowUpRightIcon(){return <ArrowRight size={14}/>}

export function Analytics({dataset}:{dataset:Dataset}) {
 const op=dataset.analysis.operations
 return <>{op.available&&<div className="mini-metrics">{[['Attendance',op.attendance_rate,'%'],['Shift coverage',op.shift_coverage,'%'],['Task completion',op.task_completion,'%'],['SLA compliance',op.sla_compliance,'%'],['Overtime',op.overtime_hours,' h'],['Open incidents',op.open_incidents,'']].map(([label,value,unit])=><div key={String(label)}><small>{label}</small><strong>{num(value as number)}{unit}</strong></div>)}</div>}<div className="inline-notice"><Sparkles size={16}/>Charts are selected from your table’s column types and computed values. Missing values and duplicates remain flagged.</div><div className="analytics-grid">{dataset.analysis.charts.map(c=><ChartPanel key={c.id} spec={c}/>)}</div>{op.available&&<Panel title="Coverage, explained" subtitle="Staff-shifts are aggregated over the selected dataset, not unique people."><DataTable rows={op.sites.map(s=>({...s}))}/><p className="panel-text text-small muted">Required staff uses the maximum requirement per site/date/shift, counted once per group. Available staff counts unique present employee IDs in each group. Repeated attendance is excluded; invalid dates, missing sites and missing shift keys are excluded from coverage. {op.duplicate_records_excluded} repeated records excluded.</p></Panel>}</>
}

function renderFormattedMessage(text?: string) {
  if (!text) return null
  const paragraphs = text.split('\n\n')
  return paragraphs.map((para, pIdx) => {
    const lines = para.split('\n')
    return (
      <p key={pIdx} className="message-paragraph" style={{ margin: '0 0 10px 0', lineHeight: '1.6' }}>
        {lines.map((line, lIdx) => {
          const parts = line.split(/(\*\*.*?\*\*)/g)
          return (
            <span key={lIdx} className="message-line">
              {parts.map((part, partIdx) => {
                if (part.startsWith('**') && part.endsWith('**')) {
                  return <strong key={partIdx} style={{ color: 'var(--c-text-strong, #ffffff)' }}>{part.slice(2, -2)}</strong>
                }
                return part
              })}
              {lIdx < lines.length - 1 && <br />}
            </span>
          )
        })}
      </p>
    )
  })
}

export function Copilot({dataset,live,onDemo,onError,onClean,onDownload,sessionMessages=[],onSessionMessagesChange}:{onClean:(column?:string|null)=>void;onDownload:(q:string,n:string)=>void;sessionMessages?:ChatMessage[];onSessionMessagesChange?:(msgs:ChatMessage[])=>void}&Base) {
  const [text, setText] = useState(''), [sending, setSending] = useState(false)
  const shown = sessionMessages
  const isFacility = Boolean(dataset?.analysis?.operations?.available)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [shown, sending])

  async function send(message: string) {
    if (!live) { onDemo(); return }
    setSending(true)
    setText('')
    const next = [...shown, { role: 'user' as const, text: message }]
    onSessionMessagesChange?.(next)

    let streamText = ''
    let assistantMessage: ChatMessage = {
      role: 'assistant',
      text: '',
      provider: 'OpsFlow AI'
    }

    try {
      const token = localStorage.getItem('opsflow.auth_token')
      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      if (token) headers['Authorization'] = `Bearer ${token}`

      const response = await fetch(apiUrl(`/api/datasets/${dataset.id}/chat/stream`), {
        method: 'POST',
        headers,
        body: JSON.stringify({ message })
      })

      if (!response.ok || !response.body) {
        const result = await post<ChatMessage>(`/api/datasets/${dataset.id}/chat`, { message })
        onSessionMessagesChange?.([...next, { ...result, role: 'assistant' }])
        return
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed.startsWith('data: ')) continue
          const payload = trimmed.slice(6).trim()
          if (!payload) continue
          try {
            const data = JSON.parse(payload)
            if (data.token) {
              streamText += data.token
              assistantMessage = {
                ...assistantMessage,
                text: streamText
              }
              onSessionMessagesChange?.([...next, assistantMessage])
            }
            if (data.done && data.message) {
              assistantMessage = {
                ...assistantMessage,
                ...data.message,
                role: 'assistant'
              }
              onSessionMessagesChange?.([...next, assistantMessage])
            }
          } catch {
            // Ignore non-json chunk
          }
        }
      }

      if (!streamText && !assistantMessage.text) {
        const result = await post<ChatMessage>(`/api/datasets/${dataset.id}/chat`, { message })
        onSessionMessagesChange?.([...next, { ...result, role: 'assistant' }])
      }
    } catch (e) {
      onError(e)
      onSessionMessagesChange?.([...next, { role: 'assistant', text: 'This request did not complete. Your data is unchanged. Please try again.' }])
    } finally {
      setSending(false)
    }
  }

  async function clearChat() {
    onSessionMessagesChange?.([])
    try { await api(`/api/datasets/${dataset.id}/chat`, { method: 'DELETE' }) } catch {}
  }

  const prompts = isFacility ? [
    { text: 'Remove missing values and clean records', tag: 'Data Sanitization' },
    { text: 'Which site has the highest absenteeism?', tag: 'Site Operations' },
    { text: 'Show overtime chart and top overtime hours', tag: 'Overtime & Fatigue' },
    { text: 'What is our overall shift coverage and staffing gap?', tag: 'Manpower Roster' }
  ] : [
    { text: 'any null and duplicates values', tag: 'Quality Check' },
    { text: 'Summarize this dataset and key patterns', tag: 'Data Summary' },
    { text: 'Show a visual chart of the data', tag: 'Visualization' },
    { text: 'Remove missing values and clean records', tag: 'Data Sanitization' }
  ]

  return (
    <div className="copilot-layout">
      <Panel className="chat-panel copilot-glow-card">
        {!shown.length ? (
          <div className="chat-welcome">
            <div className="copilot-mark glow-orb"><Sparkles size={32}/></div>
            <div className="copilot-badge-row">
              <span className="copilot-badge"><Sparkles size={11}/> YOUR OPERATIONS COPILOT</span>
            </div>
            <h2>Ask better questions.<br/><span className="copilot-glow-text">Make clearer decisions.</span></h2>
            <p className="copilot-subtitle">Explore your data in plain language. Every answer starts with facts.<br/>Every change starts with your approval.</p>
          </div>
        ) : (
          <div className="copilot-active-bar" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingBottom: '14px', marginBottom: '18px', borderBottom: '1px solid rgba(255, 255, 255, 0.08)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="copilot-badge"><Sparkles size={11}/> OPSFLOW AI COPILOT</span>
              <span style={{ fontSize: '11px', color: '#8fa89b' }}>• {shown.length} message{shown.length > 1 ? 's' : ''} in conversation</span>
            </div>
            <button className="copilot-new-chat-btn" onClick={clearChat} title="Start clean conversation">
              <RotateCcw size={12}/> New conversation
            </button>
          </div>
        )}

        {!shown.length && (
          <div className="prompt-grid">
            {prompts.map(p => (
              <button key={p.text} className="prompt-card-btn" onClick={() => void send(p.text)} disabled={sending}>
                <div className="prompt-card-top"><span className="prompt-tag">{p.tag}</span><ArrowRight size={14} className="prompt-arrow"/></div>
                <span className="prompt-text">{p.text}</span>
              </button>
            ))}
          </div>
        )}

        <div className="messages" aria-live="polite">
          {shown.map((m, i) => (
            <div className={`message ${m.role}`} key={i}>
              <span className="message-avatar">{m.role === 'user' ? 'YOU' : <Sparkles size={15}/>}</span>
              <div className="message-body">
                <div className="message-label">{m.role === 'user' ? 'You' : `OpsFlow AI · ${m.provider || 'computed facts'}`}</div>
                
                {/* 1. MESSAGE EXPLANATION AT TOP */}
                {renderFormattedMessage(m.text)}

                {/* 2. PRIMARY ACTION BUTTONS IMMEDIATELY BELOW TEXT (NOT AT THE BOTTOM OF THE TABLE) */}
                {(m.action === 'preview_cleaning' || m.download) && (
                  <div className="chat-action-cluster" style={{ display: 'flex', gap: '10px', margin: '14px 0 16px', flexWrap: 'wrap' }}>
                    {m.action === 'preview_cleaning' && (
                      <button className="button lime" onClick={() => onClean(m.column)} style={{ fontWeight: 600, boxShadow: '0 2px 8px rgba(0,0,0,0.2)' }}>
                        <ShieldCheck size={15}/> Preview changes & clean data <ArrowRight size={14}/>
                      </button>
                    )}
                    {m.download && (
                      <button className="button primary" onClick={() => onDownload(m.download!, m.download!.includes('pdf') ? 'opsflow-report.pdf' : 'opsflow-exceptions.xlsx')}>
                        <ArrowDownToLine size={15}/> Download result
                      </button>
                    )}
                  </div>
                )}

                {/* 3. CHARTS IF REQUESTED */}
                {m.chart && <ChartPanel spec={m.chart}/>}

                {/* 4. DATA TABLE AT THE BOTTOM (NICHE) IN SCROLLABLE CONTAINER */}
                {!!m.items?.length && (
                  <div className="chat-data-container" style={{ marginTop: '16px', borderRadius: '9px', border: '1px solid rgba(255, 255, 255, 0.12)', background: 'rgba(0, 0, 0, 0.18)', overflow: 'hidden' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '9px 14px', background: 'rgba(255, 255, 255, 0.04)', borderBottom: '1px solid rgba(255, 255, 255, 0.08)', fontSize: '11px', color: '#cfe5af' }}>
                      <span style={{ fontWeight: 600 }}><Database size={13} style={{ verticalAlign: '-2px', marginRight: '6px' }}/> Data Records Preview ({m.items.length} records)</span>
                      <span style={{ fontSize: '10px', color: '#8fa89b' }}>Scroll down to inspect rows</span>
                    </div>
                    <div style={{ maxHeight: '260px', overflowY: 'auto' }}>
                      <DataTable
                        rows={m.items}
                        columns={Object.keys(m.items[0]).filter(k => !['issue_id', 'confidence', 'auto_fixable', 'rule', 'suggested_value'].includes(k)).slice(0, 5)}
                      />
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}
          {sending && (
            <div className="thinking">
              <LoaderCircle size={16} className="spin"/>
              <span>Analyzing dataset with intelligent streaming…</span>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
        <form className="chat-input copilot-input-bar" onSubmit={e => { e.preventDefault(); if (text.trim()) void send(text) }}>
          <input
            aria-label="Ask your data"
            value={text}
            onChange={e => setText(e.target.value)}
            maxLength={1500}
            placeholder={live ? (isFacility ? 'Ask about site coverage, absenteeism, quality, or request a chart…' : 'Ask about missing values, distributions, columns, or request a chart…') : 'Load the demo to start a conversation…'}
            disabled={sending}
          />
          <button className="button primary copilot-send-btn" aria-label="Send message" disabled={sending || !text.trim()}>
            <Send size={17}/>
          </button>
        </form>
        <div className="chat-disclaimer">
          <ShieldCheck size={13}/>Zero hallucination · Safe deterministic tools · Your original data remains unchanged
        </div>
      </Panel>
      <div className="copilot-side">
        <Panel className="copilot-side-panel" title="Connected context">
          <div className="context-file">
            <FileSpreadsheet size={24}/>
            <b>{dataset.filename}</b>
            <small>{num(dataset.analysis.rows)} records · version {dataset.version}</small>
            <Badge tone={live ? 'success' : 'warning'}>{live ? 'Ready to explore' : 'Preview · load demo first'}</Badge>
          </div>
        </Panel>
        <Panel className="copilot-side-panel" title="Built for trust">
          <ul className="trust-list">
            <li><Check size={16}/>Calculations run in Python (100% deterministic)</li>
            <li><Check size={16}/>AI receives aggregates & schema, not raw secrets</li>
            <li><Check size={16}/>Cleaning requires user confirmation</li>
            <li><Check size={16}/>Works when external AI is unavailable</li>
          </ul>
        </Panel>
      </div>
    </div>
  )
}

export function Reports({dataset,onDownload}:{dataset:Dataset;onDownload:(q:string,n:string)=>void}) {
 const [period,setPeriod]=useState('all')
 return <><div className="reports-intro"><div><span className="eyebrow">READY-TO-SHARE EXECUTIVE REPORTS</span><h2>Clear reports for your<br/>team & clients.</h2><p>Download clean, professional PDF summaries in simple everyday language — no confusing math formulas or statistical jargon.</p></div><div className="report-preview"><div className="report-page"><span>OPSFLOW AI</span><b>Operations<br/>at a glance.</b><div className="report-lines"/><div className="paper-chart">{[40,66,48,85,72].map((h,i)=><i key={i} style={{height:h}}/>)}</div><small>ACCURATE · VERIFIED · EASY TO READ</small></div></div></div><div className="reports-toolbar"><div><h3>Executive PDF Reports</h3><p>Choose your reporting timeframe. Download polished, meeting-ready PDF documents.</p></div><select aria-label="Report period" value={period} onChange={e=>setPeriod(e.target.value)}><option value="all">All records (Full dataset)</option><option value="daily">Daily summary (Latest day)</option><option value="weekly">Weekly summary (Past 7 days)</option><option value="monthly">Monthly summary (Past 30 days)</option></select></div><div className="report-grid">{[{id:'daily',name:'Operations MIS',badge:'DAILY SUMMARY',desc:'Full operational picture: staff attendance rates, site-by-site staffing coverage, overtime hours, and recommended next steps.',icon:FileText,btn:'Download Operations PDF'},{id:'quality',name:'Data Quality Report',badge:'DATA HEALTH',desc:'Honest health check of your data: highlights missing values, duplicate entries, typos, and safe automatic fixes.',icon:ShieldCheck,btn:'Download Quality PDF'},{id:'exceptions',name:'Exception Report',badge:'ACTION CHECKLIST',desc:'Urgent items needing attention: staffing shortages, absent personnel, SLA target breaches, and unusual values.',icon:Database,btn:'Download Exceptions PDF'}].map(r=><Panel key={r.id} className="report-card"><div className="report-icon"><r.icon size={23}/></div><Badge>{r.badge}</Badge><h3>{r.name}</h3><p>{r.desc}</p><button className="button secondary full" onClick={()=>onDownload(`format=pdf&report=${r.id}&period=${period}`,`opsflow-${r.id}.pdf`)}><ArrowDownToLine size={16}/>{r.btn}</button></Panel>)}</div><Panel title="Export Clean Data & Spreadsheets" subtitle={`Version ${dataset.version} · Original files preserved · Formula-safe exports for Excel & BI`}><div className="export-grid">{[['Clean CSV','csv','data','Standard CSV format for any tool'],['Clean Excel','xlsx','data','Formatted Microsoft Excel (.xlsx) workbook'],['Flagged Issues','xlsx','issues','Excel spreadsheet of all items needing review'],['Audit Trail','csv','audit','Full record of every approved change made']].map(([name,fmt,kind,sub])=><button key={name} onClick={()=>onDownload(`format=${fmt}&kind=${kind}`,`opsflow-${kind}.${fmt}`)}><FileSpreadsheet size={23}/><div><b>{name}</b><small>{sub}</small></div><ArrowDownToLine size={17}/></button>)}</div></Panel></>
}

export function History({jobs,onOpen}:{jobs:Job[];onOpen:(id:string)=>void}) {
 return <Panel title="Every run has a story" subtitle="Sources, processing results and status for this workspace. Runtime history is temporary."><div className="history-list">{jobs.map(j=><div className="history-item" key={j.id}><div className="history-icon"><FileSpreadsheet size={22}/></div><div><h4>{j.filename}</h4><p>{new Date(j.created*1000).toLocaleString()} · {j.id.slice(0,8)}</p><div className="history-facts"><span>{num(j.rows)} records</span><span>{num(j.issues)} issues at import</span><span>{j.quality_before??'—'}% original quality</span><span>{j.duration??'—'}s processing</span></div>{j.error&&<p className="error-text">{j.error}</p>}</div><Badge tone={j.status==='completed'?'success':j.status==='failed'?'critical':'warning'}>{human(j.status)}</Badge>{j.dataset_id&&<button className="button secondary small" onClick={()=>onOpen(j.dataset_id!)}>Open run<ArrowRight size={14}/></button>}</div>)}{!jobs.length&&<div className="empty"><FileText size={28}/><p>Your first run starts with an upload or the demo workspace.</p></div>}</div></Panel>
}

export function SystemStatus({status,onTest,testing}:{status?:Status;onTest:()=>void;testing:boolean}) {
 return <><div className="system-banner"><div className={`system-orb ${status?'ready':''}`}><ShieldCheck size={30}/></div><div><h2>{status?'Your workspace is ready.':'Connecting to your backend…'}</h2><p>{status?'Deterministic processing is available. AI is optional.':'The interface stays available during a cold start. Retrying in the background.'}</p></div><Badge tone={status?'success':'warning'}>{status?'Backend online':'Waking up'}</Badge></div><div className="two-grid"><Panel title="Processing & storage"><dl className="status-list"><div><dt>Backend</dt><dd>{status?.backend||'Connecting'}</dd></div><div><dt>Version</dt><dd>{status?.version||'—'}</dd></div><div><dt>Database</dt><dd>{status?.database||'Waiting for readiness'}</dd></div><div><dt>Job queue</dt><dd>{status?`${status.queue} / ${status.queue_limit}`:'—'}</dd></div><div><dt>Upload limit</dt><dd>{status?`${status.max_upload_mb} MB · ${num(status.max_rows)} rows`:'—'}</dd></div></dl><div className="inline-notice">{status?.persistence||'Runtime history and uploads are temporary. Download important outputs.'}</div></Panel><Panel title="Data capabilities"><div className="capabilities">{['CSV','XLSX','XLS','Native PDF','Public Google Sheets'].map(f=><div key={f}><FileSpreadsheet size={18}/><b>{f}</b><Badge tone="success">Supported</Badge></div>)}</div><p className="panel-text text-small muted">Scanned PDF OCR is unavailable. Password-protected workbooks need an unlocked copy. Unsupported files fail safely.</p></Panel></div><Panel title="AI providers" subtitle="Explicit checks only. No background token-consuming health calls." action={<button className="button primary" onClick={onTest} disabled={testing||!status}>{testing?<LoaderCircle size={16} className="spin"/>:<Sparkles size={16}/>}Test AI providers</button>}><div className="provider-grid">{Object.entries(status?.providers||{}).map(([name,p])=><div className="provider-card" key={name}><div className="provider-head"><div className="provider-logo">{name==='groq'?'g.':'✦'}</div><div><h3>{human(name)}</h3><small>{p.model}</small></div><Badge tone={p.last_success?'success':p.configured?'warning':'neutral'}>{p.last_success?'Verified':p.configured?'Configured':'No key'}</Badge></div><dl className="status-list"><div><dt>API reachable</dt><dd>{p.reachable===null?'Not tested':p.reachable?'Yes':'No'}</dd></div><div><dt>Model available</dt><dd>{p.model_available===null?'Not tested':p.model_available?'Yes':'No'}</dd></div><div><dt>Last latency</dt><dd>{p.latency_ms===null?'—':`${p.latency_ms} ms`}</dd></div><div><dt>Last success</dt><dd>{p.last_success?new Date(p.last_success*1000).toLocaleTimeString():'Not yet'}</dd></div><div><dt>Last failure</dt><dd>{p.failure?human(p.failure):'None recorded'}</dd></div><div><dt>Circuit</dt><dd>{p.circuit_open?'Cooling down':'Closed'}</dd></div></dl></div>)}</div><div className="panel-bottom"><ShieldCheck size={15}/><span>Sequential fallback · provider-level cooldown on rate limits · no keys exposed</span></div></Panel></>
}
