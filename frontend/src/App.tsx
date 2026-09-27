import { useEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Activity, ArrowRight, Bell, ChartNoAxesCombined, Check, ChevronDown, CircleHelp, Database, FileText, GitBranch, History as HistoryIcon, Layers3, LayoutDashboard, LoaderCircle, LockKeyhole, LogOut, Menu, RotateCcw, Search, ShieldCheck, Sparkles, TriangleAlert, Upload, User as UserIcon, X } from 'lucide-react'
import { AnimatePresence, motion, MotionConfig } from 'framer-motion'
import { api, apiUrl, download, post, setAuthToken } from './api'
import { Badge, DataTable, display, human, Modal, num } from './components'
import Overview from './Overview'
import { Analytics, Copilot, History, Quality, Reports, Sources, SystemStatus } from './WorkspacePages'
import type { AuthResponse, ChatMessage, Dataset, Issue, Job, Row, Status, Summary, User } from './types'

const navigation = [
  { name: 'Overview', icon: LayoutDashboard },
  { name: 'Data Sources', icon: Database },
  { name: 'Analytics', icon: ChartNoAxesCombined },
  { name: 'AI Copilot', icon: Sparkles },
  { name: 'Reports', icon: FileText },
  { name: 'Data Quality', icon: ShieldCheck },
  { name: 'Exceptions', icon: TriangleAlert },
  { name: 'Run History', icon: HistoryIcon },
  { name: 'System Status', icon: Activity }
]
const headings: Record<string, [string, string]> = {
  'Overview': ['Operations overview', 'The big picture. The details that matter.'],
  'Data Sources': ['Connect your data', 'Spreadsheets, documents and sheets. One connected workspace.'],
  'AI Copilot': ['A little less spreadsheet. A little more clarity.', 'Your operational questions, answered with evidence.'],
  'Data Quality': ['Good decisions start with trusted data', 'Understand the issues. Review the changes. Keep the originals.'],
  'Exceptions': ['Bring the important things into focus', 'A clear view of what needs human attention.'],
  'Analytics': ['The story behind the numbers', 'Schema-aware charts. Deterministic calculations. Practical insight.'],
  'Reports': ['Insights, ready to share', 'Turn this dataset into a management-ready report.'],
  'Run History': ['Your operations, traced', 'Every import, every result, every processing run.'],
  'System Status': ['Confidence, built in', 'Readiness, limits and provider health. Nothing hidden.']
}

export default function App() {
  const queryClient = useQueryClient()
  const [page, setPage] = useState('Overview'), [mobile, setMobile] = useState(false), [datasetId, setDatasetId] = useState(localStorage.getItem('opsflow.dataset') || ''), [error, setError] = useState(''), [notice, setNotice] = useState(''), [busy, setBusy] = useState(false), [cleanOpen, setCleanOpen] = useState(false), [cleanColumn, setCleanColumn] = useState<string | null>(null), [summary, setSummary] = useState<Summary>(), [searchOpen, setSearchOpen] = useState(false), [search, setSearch] = useState(''), [guide, setGuide] = useState(false), [auditOpen, setAuditOpen] = useState(false)
  const [user, setUser] = useState<User | null>(null), [authOpen, setAuthOpen] = useState(false), [authMode, setAuthMode] = useState<'login' | 'register'>('login'), [authEmail, setAuthEmail] = useState(''), [authPassword, setAuthPassword] = useState(''), [authName, setAuthName] = useState(''), [authError, setAuthError] = useState(''), [authBusy, setAuthBusy] = useState(false)
  const [cleanMode, setCleanMode] = useState(localStorage.getItem('opsflow.clean_mode') === 'true')
  const [cleanConfirmOpen, setCleanConfirmOpen] = useState(false)
  const [sessionChats, setSessionChats] = useState<Record<string, ChatMessage[]>>({})
  const pending = useRef<string | null>(null), pendingClean = useRef(false), autoDemoTriggered = useRef(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [cleanDrag, setCleanDrag] = useState(false)
  const [wakeSeconds, setWakeSeconds] = useState(0)
  const [showWakeup, setShowWakeup] = useState(false)
  const [wakeSuccess, setWakeSuccess] = useState(false)
  const [wakeDismissed, setWakeDismissed] = useState(false)
  const triggerUpload = () => {
    fileInputRef.current?.click()
  }

  // Immediate wake-up trigger when user visits (activates Render web service)
  useEffect(() => {
    fetch(apiUrl('/health')).catch(() => {})
  }, [])

  const status = useQuery({
    queryKey: ['status'],
    queryFn: () => api<Status>('/api/status'),
    refetchInterval: q => (q.state.data ? 15000 : 3000),
    retry: Infinity,
  })

  useEffect(() => {
    if (status.data) {
      if (showWakeup && !wakeSuccess) {
        setWakeSuccess(true)
        const t = setTimeout(() => setShowWakeup(false), 1600)
        return () => clearTimeout(t)
      }
      return
    }

    const interval = setInterval(() => {
      setWakeSeconds(s => {
        const next = s + 1
        if (next >= 2 && !wakeDismissed) {
          setShowWakeup(true)
        }
        return next
      })
    }, 1000)

    return () => clearInterval(interval)
  }, [status.data, showWakeup, wakeSuccess, wakeDismissed])
  const preview = useQuery({ queryKey: ['preview'], queryFn: () => fetch('/demo-preview.json').then(r => r.json() as Promise<Dataset>), staleTime: Infinity, enabled: !cleanMode })
  const jobs = useQuery({ queryKey: ['jobs', user?.id || 'guest'], queryFn: () => api<{ items: Job[] }>('/api/jobs'), enabled: !!status.data, refetchInterval: q => q.state.data?.items.some(j => ['queued', 'processing'].includes(j.status)) ? 750 : 4000 })
  const current = useQuery({ queryKey: ['dataset', datasetId], queryFn: () => api<Dataset>(`/api/datasets/${datasetId}`), enabled: !!datasetId && !!status.data, retry: 0 })
  const audit = useQuery({ queryKey: ['audit', datasetId, current.data?.version], queryFn: () => api<{ items: Row[] }>(`/api/datasets/${datasetId}/audit`), enabled: auditOpen && !!current.data })

  const dataset = (!cleanMode ? (current.data || preview.data) : current.data), live = !!current.data

  useEffect(() => {
    api<{ authenticated: boolean; user: User | null }>('/api/auth/me')
      .then(res => {
        if (res.authenticated && res.user) setUser(res.user)
        else setUser(null)
      })
      .catch(() => setUser(null))
  }, [])

  const selectDataset = (id: string) => { setDatasetId(id); localStorage.setItem('opsflow.dataset', id); setSummary(undefined); setError('') }
  const navigate = (p: string) => { setPage(p); setMobile(false); window.scrollTo({ top: 0, behavior: 'instant' }) }
  const fail = (e: unknown) => { setError(e instanceof Error ? e.message : 'This action could not finish. Try again.'); setBusy(false) }

  useEffect(() => {
    const job = jobs.data?.items.find(j => j.id === pending.current)
    if (job?.status === 'completed' && job.dataset_id) {
      pending.current = null
      setDatasetId(job.dataset_id)
      localStorage.setItem('opsflow.dataset', job.dataset_id)
      setSummary(undefined)
      setBusy(false)
      setNotice('Your data is ready. Originals are preserved.')
      if (pendingClean.current) { pendingClean.current = false; setCleanOpen(true) }
    } else if (job?.status === 'failed') {
      pending.current = null
      setBusy(false)
      setError(job.error || 'Processing failed. Please try another file.')
    } else if (job?.status === 'awaiting_selection') {
      setBusy(false)
      setPage('Data Sources')
    }
  }, [jobs.data])

  useEffect(() => { if (!notice) return; const id = setTimeout(() => setNotice(''), 5000); return () => clearTimeout(id) }, [notice])
  useEffect(() => { function key(e: KeyboardEvent) { if ((e.ctrlKey || e.metaKey) && e.key === 'k') { e.preventDefault(); setSearchOpen(v => !v) } } window.addEventListener('keydown', key); return () => window.removeEventListener('keydown', key) }, [])

  async function demo(silent = false) {
    setCleanMode(false)
    localStorage.removeItem('opsflow.clean_mode')
    if (!silent) setBusy(true)
    setError('')
    try {
      const j = await post<Job>('/api/demo')
      if (j.status === 'completed' && j.dataset_id) {
        selectDataset(j.dataset_id)
        if (!silent) setBusy(false)
        if (pendingClean.current) { pendingClean.current = false; setCleanOpen(true) }
      } else {
        pending.current = j.id
        await queryClient.invalidateQueries({ queryKey: ['jobs'] })
      }
    } catch (e) {
      if (!silent) fail(e)
    }
  }

  // Automatically load demo dataset on first visit so recruiters and users immediately see full data and features
  useEffect(() => {
    if (status.data && !datasetId && !cleanMode && !autoDemoTriggered.current) {
      autoDemoTriggered.current = true
      void demo(true)
    }
  }, [status.data, datasetId, cleanMode])

  function openClean(column?: string | null) {
    setCleanColumn(column || null)
    if (!live) { pendingClean.current = true; void demo() }
    else setCleanOpen(true)
  }

  async function files(items: File[]) {
    navigate('Data Sources')
    setError('')
    for (const file of items.slice(0, 8)) {
      try {
        if (file.size > 10 * 1024 * 1024) throw new Error(`${file.name} exceeds 10 MB. Split it before importing.`)
        const form = new FormData()
        form.append('file', file)
        const j = await api<Job>('/api/uploads', { method: 'POST', body: form })
        if (j.status === 'completed' && j.dataset_id) selectDataset(j.dataset_id)
        else pending.current = j.id
        await queryClient.invalidateQueries({ queryKey: ['jobs'] })
      } catch (e) { fail(e) }
    }
    if (items.length > 8) setError('Up to eight files can be queued at once. Import the remaining files after these finish.')
  }

  async function sheet(url: string) {
    setBusy(true)
    try {
      const j = await post<Job>('/api/sheets', { url })
      if (j.dataset_id) selectDataset(j.dataset_id)
      else pending.current = j.id
      await queryClient.invalidateQueries({ queryKey: ['jobs'] })
      setBusy(false)
    } catch (e) { fail(e) }
  }

  async function select(job: Job, table: number) {
    try {
      await post(`/api/jobs/${job.id}/select`, { table })
      pending.current = job.id
      await queryClient.invalidateQueries({ queryKey: ['jobs'] })
    } catch (e) { fail(e) }
  }

  async function exportFile(q: string, name: string) {
    if (!live) { setNotice('Load the demo workspace first to generate a real export.'); await demo(); return }
    setBusy(true)
    try {
      await download(`/api/datasets/${datasetId}/export?${q}`, name)
      setNotice('Your export is ready.')
      setBusy(false)
    } catch (e) { fail(e) }
  }

  async function getSummary() {
    if (!live) { await demo(); return }
    setBusy(true)
    try {
      setSummary(await post<Summary>(`/api/datasets/${datasetId}/summary`))
      setBusy(false)
    } catch (e) { fail(e) }
  }

  async function testProviders() {
    setBusy(true)
    try {
      await post('/api/providers/test')
      await queryClient.invalidateQueries({ queryKey: ['status'] })
      setBusy(false)
      setNotice('Provider diagnostics completed. Results are shown below.')
    } catch (e) { fail(e) }
  }

  async function handleDemoLogin() {
    setAuthBusy(true)
    setAuthError('')
    try {
      const res = await post<AuthResponse>('/api/auth/demo-login')
      setAuthToken(res.token)
      setUser(res.user)
      setSessionChats({})
      setAuthOpen(false)
      setAuthEmail('')
      setAuthPassword('')
      setAuthName('')
      setDatasetId('')
      localStorage.removeItem('opsflow.dataset')
      setCleanMode(true)
      localStorage.setItem('opsflow.clean_mode', 'true')
      await queryClient.invalidateQueries()
      setNotice('⚡ Fast Demo Login active. Your clean workspace is ready for your data.')
    } catch (err) {
      setAuthError(err instanceof Error ? err.message : 'Demo login failed')
    } finally {
      setAuthBusy(false)
    }
  }

  async function handleAuth(e: React.FormEvent) {
    e.preventDefault()
    setAuthError('')
    setAuthBusy(true)
    try {
      const endpoint = authMode === 'register' ? '/api/auth/register' : '/api/auth/login'
      const payload = authMode === 'register' ? { email: authEmail, password: authPassword, name: authName } : { email: authEmail, password: authPassword }
      const res = await post<AuthResponse>(endpoint, payload)
      setAuthToken(res.token)
      setUser(res.user)
      setSessionChats({})
      setAuthOpen(false)
      setAuthEmail('')
      setAuthPassword('')
      setAuthName('')
      setDatasetId('')
      localStorage.removeItem('opsflow.dataset')
      setCleanMode(true)
      localStorage.setItem('opsflow.clean_mode', 'true')
      await queryClient.invalidateQueries()
      setNotice(`Signed in as ${res.user.name || res.user.email}. Fresh clean workspace loaded.`)
    } catch (err) {
      setAuthError(err instanceof Error ? err.message : 'Authentication failed')
    } finally {
      setAuthBusy(false)
    }
  }

  async function handleLogout() {
    setBusy(true)
    try {
      await post('/api/auth/logout')
    } catch {
      // ignore
    } finally {
      setAuthToken(null)
      setUser(null)
      setDatasetId('')
      setSessionChats({})
      localStorage.removeItem('opsflow.dataset')
      await queryClient.invalidateQueries()
      setBusy(false)
      setNotice('Signed out. Switched to demo workspace.')
    }
  }

  async function setCleanWorkspace(wipeData = false) {
    if (wipeData) {
      setBusy(true)
      try {
        await post('/api/workspace/clean')
        await queryClient.invalidateQueries({ queryKey: ['jobs'] })
        setNotice('Workspace data cleared. Fresh slate.')
      } catch (e) { fail(e) }
      finally { setBusy(false) }
    }
    setDatasetId('')
    setSessionChats({})
    localStorage.removeItem('opsflow.dataset')
    setCleanMode(true)
    localStorage.setItem('opsflow.clean_mode', 'true')
    setCleanConfirmOpen(false)
    if (!wipeData) {
      setNotice('Clean workspace mode active. Ready for your own data files.')
    }
  }

  function loadDemoData() {
    setCleanMode(false)
    localStorage.removeItem('opsflow.clean_mode')
    void demo()
  }

  const jobList = jobs.data?.items || [], active = jobList.find(j => ['queued', 'processing'].includes(j.status))

  return (
    <MotionConfig reducedMotion="user">
      <div className="app-shell">
        {mobile && <button className="nav-backdrop" aria-label="Close navigation" onClick={() => setMobile(false)} />}
        <aside className={`sidebar ${mobile ? 'open' : ''}`}>
          <a className="brand" href="#" onClick={e => { e.preventDefault(); navigate('Overview') }}>
            <span className="brand-mark"><GitBranch size={23} /></span>
            <span>OpsFlow<span className="brand-ai">AI</span></span>
          </a>

          <div className="workspace-card">
            <div className="workspace-avatar">{user ? user.name.slice(0, 1).toUpperCase() : 'O'}</div>
            <div>
              <b>{user ? user.name : 'Operations workspace'}</b>
              <span>{user ? `${user.email} · Isolated` : 'Business intelligence, simplified'}</span>
            </div>
          </div>

          <div className="nav-label">WORKSPACE</div>
          <nav>
            {navigation.map(({ name, icon: Icon }, i) => (
              <div key={name}>
                {i === 2 && <div className="nav-label section-label">INTELLIGENCE</div>}
                {i === 6 && <div className="nav-label section-label">REPORTING & AUDIT</div>}
                {i === 8 && <div className="nav-label section-label">WORKSPACE HEALTH</div>}
                <button className={`nav-item ${page === name ? 'active' : ''}`} aria-current={page === name ? 'page' : undefined} onClick={() => navigate(name)}>
                  <Icon size={18} />
                  <span>{name}</span>
                  {name === 'Exceptions' && dataset && <span className="nav-count">{dataset.analysis.severity.critical}</span>}
                  {name === 'AI Copilot' && <span className="ai-label">AI</span>}
                </button>
              </div>
            ))}
          </nav>

          <div className="sidebar-bottom">
            <div className="safe-note">
              <ShieldCheck size={19} />
              <b>Built for peace of mind.</b>
              <p>Originals preserved.<br />Every change traceable.</p>
              <button onClick={() => setGuide(true)}>How OpsFlow works<ArrowUpRightSmall /></button>
            </div>

            {user ? (
              <div className="session-button user-session-active">
                <span className="session-avatar user-avatar-active">{user.name.slice(0, 2).toUpperCase()}</span>
                <span>
                  <b>{user.name}</b>
                  <small>{user.email} · Private</small>
                </span>
                <button className="text-button logout-btn" title="Sign out" onClick={(e) => { e.stopPropagation(); void handleLogout() }}>
                  <LogOut size={13} /> Sign out
                </button>
              </div>
            ) : (
              <button className="session-button" onClick={() => { setAuthMode('login'); setAuthOpen(true) }}>
                <span className="session-avatar">DW</span>
                <span><b>Demo workspace</b><small>Click to sign in & isolate</small></span>
                <ChevronDown size={15} />
              </button>
            )}
          </div>
        </aside>

        <div className="app-main">
          <header className="topbar">
            <div className="breadcrumb">
              <button className="icon-button mobile-menu" aria-label="Open navigation" onClick={() => setMobile(true)}><Menu size={20} /></button>
              <span>Workspace</span>
              <ChevronRightSmall />
              <strong>{page}</strong>
              <div className="grace-topbar-pill" title="OpsFlow Prototype built for Grace Facility Services">
                <span className="grace-pulse-dot" />
                <span>Prototype for Grace Facility Service</span>
              </div>
            </div>

            <div className="topbar-actions">
              {!cleanMode ? (
                <button className="button secondary small topbar-clean-btn" onClick={() => setCleanConfirmOpen(true)} title="Clear demo data and start fresh">
                  <RotateCcw size={14} /><span>Clean Workspace</span>
                </button>
              ) : (
                <button className="button secondary small topbar-clean-btn" onClick={loadDemoData} title="Load synthetic demo data">
                  <Sparkles size={14} /><span>Load Demo Data</span>
                </button>
              )}

              {user ? (
                <button className="user-profile-badge" onClick={() => setAuthOpen(true)} title={`Signed in as ${user.email}`}>
                  <span className="user-avatar-circle">{user.name.slice(0, 2).toUpperCase()}</span>
                  <span>{user.name}</span>
                  <Badge tone="success">Isolated</Badge>
                </button>
              ) : (
                <div className="auth-nav-cluster">
                  <button className="button secondary small login-trigger" onClick={() => { setAuthMode('login'); setAuthOpen(true) }}>
                    <UserIcon size={14} />
                    <span>Sign In / Register</span>
                  </button>
                  <button className="button lime small demo-login-nav-btn" onClick={() => void handleDemoLogin()} disabled={authBusy} title="Fast 1-click Demo Login (Clean Start)">
                    <Sparkles size={13} />
                    <span>Demo-Login</span>
                  </button>
                </div>
              )}

              <button className="top-search" onClick={() => setSearchOpen(true)}><Search size={15} /><span>Jump to a page</span><kbd>⌘ K</kbd></button>
              <button className="connection-status" onClick={() => navigate('System Status')}><i className={`small-dot ${status.data ? 'online' : 'pending'}`} />{status.data ? 'System ready' : 'Waking backend…'}</button>
              <span className="top-divider" />
              <button className="icon-button" aria-label="Product walkthrough" onClick={() => setGuide(true)}><CircleHelp size={19} /></button>
              <button className="icon-button" aria-label="View active jobs" onClick={() => navigate('Data Sources')}><Bell size={19} />{active && <span className="notification-dot" />}</button>
            </div>
          </header>

          <main className="main-content" id="main-content">
            <div className="page-heading">
              <div>
                <div className="eyebrow">YOUR OPERATIONS, UNDERSTOOD.</div>
                <h1>{headings[page][0]}</h1>
                <p>{headings[page][1]}</p>
              </div>
              <div className="page-actions">
                {!cleanMode ? (
                  <button className="button secondary" onClick={() => setCleanConfirmOpen(true)}>
                    <RotateCcw size={15} />Clean Workspace
                  </button>
                ) : (
                  <button className="button secondary" onClick={loadDemoData}>
                    <Sparkles size={15} />Load Demo Data
                  </button>
                )}
                {live && (
                  <select className="dataset-select" aria-label="Active dataset" value={datasetId} onChange={e => selectDataset(e.target.value)}>
                    {jobList.filter(j => j.dataset_id).map(j => (
                      <option value={j.dataset_id} key={j.id}>{j.filename}</option>
                    ))}
                  </select>
                )}
                <button className="button primary" onClick={triggerUpload}>
                  <Upload size={16} />Upload data
                </button>
              </div>
            </div>

            <input ref={fileInputRef} type="file" multiple accept=".csv,.xlsx,.xls,.pdf" hidden onChange={e => { void files(Array.from(e.target.files || [])); e.target.value = '' }} />

            {(error || current.error) && (
              <div className="error-banner" role="alert">
                <TriangleAlert size={20} />
                <div>
                  <b>Let’s get this back on track.</b>
                  <p>{error || current.error?.message}</p>
                  <small>Original data has not been changed by this failed operation.</small>
                </div>
                <button className="icon-button" aria-label="Dismiss error" onClick={() => { setError(''); if (current.error) { setDatasetId(''); localStorage.removeItem('opsflow.dataset') } }}>
                  <X size={17} />
                </button>
              </div>
            )}

            {active && (
              <div className="active-job" role="status">
                <LoaderCircle size={17} className="spin" />
                <b>{active.stage}</b>
                <span>{active.filename}</span>
                <div className="progress-track"><div style={{ width: active.progress + '%' }} /></div>
                <small>{active.progress}%</small>
              </div>
            )}

            <AnimatePresence mode="wait">
              <motion.div key={page} className="page-body" initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: .14 }}>
                {page === 'Data Sources' && (
                  <Sources
                    key={dataset?.id || 'empty-sources'}
                    dataset={dataset}
                    live={live}
                    onError={fail}
                    onDemo={() => void demo()}
                    onFiles={f => void files(f)}
                    onSheet={u => void sheet(u)}
                    jobs={jobList}
                    onSelect={(j, t) => void select(j, t)}
                    onOpen={selectDataset}
                  />
                )}

                {page === 'Run History' && (
                  <History jobs={jobList} onOpen={id => { selectDataset(id); navigate('Overview') }} />
                )}

                {page === 'System Status' && (
                  <SystemStatus status={status.data} onTest={() => void testProviders()} testing={busy} />
                )}

                {page === 'Overview' && (
                  dataset ? (
                    <Overview
                      dataset={dataset}
                      live={live}
                      onUpload={triggerUpload}
                      onDemo={() => void demo()}
                      onClean={() => openClean()}
                      onNavigate={navigate}
                      summary={summary}
                      onSummary={() => void getSummary()}
                      busy={busy}
                    />
                  ) : cleanMode ? (
                    <div
                      className={`clean-hero-card ${cleanDrag ? 'dragging' : ''}`}
                      onDragOver={e => { e.preventDefault(); setCleanDrag(true) }}
                      onDragLeave={() => setCleanDrag(false)}
                      onDrop={e => {
                        e.preventDefault()
                        setCleanDrag(false)
                        if (e.dataTransfer.files.length) void files(Array.from(e.dataTransfer.files))
                      }}
                    >
                      <div className="clean-hero-content">
                        <div className="eyebrow light"><span className="tiny-line" /> FRESH START · ISOLATED DATA</div>
                        <h2>Clean Workspace.<br /><span>Ready for your data.</span></h2>
                        <p>No demo data is loaded. Connect your CSVs, Excel workbooks, or native PDFs to start profiling and cleaning with deterministic rules and grounded AI.</p>
                        <div className="story-buttons">
                          <button className="button lime" onClick={triggerUpload}><Upload size={16} />Upload your data<ArrowUpRightSmall /></button>
                          <button className="button story-ghost" onClick={loadDemoData} disabled={busy}><Database size={15} />Load synthetic demo data<ArrowRight size={14} /></button>
                        </div>
                      </div>
                      <div className="clean-features">
                        <div className="clean-feature-item"><LockKeyhole size={18} /><div><b>Private & Isolated</b><p>Every account has its own isolated SQLite workspace. Zero cross-tenant leakage.</p></div></div>
                        <div className="clean-feature-item"><ShieldCheck size={18} /><div><b>Originals Preserved</b><p>Your raw uploads are never overwritten. Every change is an approved version.</p></div></div>
                        <div className="clean-feature-item"><Sparkles size={18} /><div><b>Zero Hallucination AI</b><p>Deterministic calculations run directly on your data. AI never invents numbers.</p></div></div>
                      </div>
                    </div>
                  ) : (
                    <div className="initial-shell">
                      <div className="story-card">
                        <div className="story-copy">
                          <h2>Messy data.<br />Clear decisions.</h2>
                          <p>Your operations workspace is getting ready.</p>
                        </div>
                      </div>
                      <div className="metrics-grid">
                        {[1, 2, 3, 4].map(n => <div className="metric-card skeleton" key={n} />)}
                      </div>
                      {preview.error && <button className="button secondary" onClick={() => void preview.refetch()}>Retry workspace preview</button>}
                    </div>
                  )
                )}

                {page === 'AI Copilot' && (
                  dataset ? (
                    <Copilot
                      key={dataset.id}
                      dataset={dataset}
                      live={live}
                      onError={fail}
                      onDemo={() => void demo()}
                      onClean={openClean}
                      onDownload={(q, n) => void exportFile(q, n)}
                      sessionMessages={sessionChats[dataset.id] || []}
                      onSessionMessagesChange={msgs => setSessionChats(prev => ({ ...prev, [dataset.id]: msgs }))}
                    />
                  ) : (
                    <div className="clean-hero-card">
                      <div className="clean-hero-content">
                        <div className="eyebrow light"><span className="tiny-line" /> AI OPERATIONS COPILOT</div>
                        <h2>Connect your data<br /><span>to start asking.</span></h2>
                        <p>AI Copilot analyzes your specific operations dataset using deterministic Python rules. Upload a CSV or Excel file to begin asking questions, or load the demo dataset.</p>
                        <div className="story-buttons">
                          <button className="button lime" onClick={triggerUpload}><Upload size={16} />Upload your data<ArrowUpRightSmall /></button>
                          <button className="button story-ghost" onClick={loadDemoData} disabled={busy}><Database size={15} />Load synthetic demo data<ArrowRight size={14} /></button>
                        </div>
                      </div>
                      <div className="clean-features">
                        <div className="clean-feature-item"><Sparkles size={18} /><div><b>Deterministic Calculations</b><p>100% grounded in your actual records. Zero hallucinations.</p></div></div>
                        <div className="clean-feature-item"><LockKeyhole size={18} /><div><b>Zero Data Leakage</b><p>Your data stays within your private session or user account.</p></div></div>
                      </div>
                    </div>
                  )
                )}

                {(page === 'Data Quality' || page === 'Exceptions') && (
                  dataset ? (
                    <>
                      <div className="section-tools">
                        <span><Badge tone={live ? 'success' : 'neutral'}>{live ? 'Live dataset' : 'Synthetic preview'}</Badge>Version {dataset.version}</span>
                        <button className="text-button" onClick={() => setAuditOpen(true)}><HistoryIcon size={15} />What changed? View audit trail</button>
                      </div>
                      <Quality key={page} dataset={dataset} live={live} onClean={() => openClean()} onDownload={(q, n) => void exportFile(q, n)} exceptions={page === 'Exceptions'} />
                    </>
                  ) : (
                    <div className="clean-hero-card">
                      <div className="clean-hero-content">
                        <div className="eyebrow light"><span className="tiny-line" /> DATA QUALITY & EXCEPTIONS</div>
                        <h2>Quality findings require<br /><span>an uploaded dataset.</span></h2>
                        <p>Upload your operational data to discover formatting errors, shift coverage gaps, and invalid dates with deterministic rule profiling.</p>
                        <div className="story-buttons">
                          <button className="button lime" onClick={triggerUpload}><Upload size={16} />Upload your data<ArrowUpRightSmall /></button>
                          <button className="button story-ghost" onClick={loadDemoData} disabled={busy}><Database size={15} />Load synthetic demo data<ArrowRight size={14} /></button>
                        </div>
                      </div>
                      <div className="clean-features">
                        <div className="clean-feature-item"><ShieldCheck size={18} /><div><b>Originals Never Modified</b><p>Safe transformations create traceable new versions.</p></div></div>
                      </div>
                    </div>
                  )
                )}

                {page === 'Analytics' && (
                  dataset ? (
                    <Analytics dataset={dataset} />
                  ) : (
                    <div className="clean-hero-card">
                      <div className="clean-hero-content">
                        <div className="eyebrow light"><span className="tiny-line" /> ANALYTICS & CHARTS</div>
                        <h2>Schema-aware analytics<br /><span>ready for your data.</span></h2>
                        <p>Upload a file to generate attendance charts, shift coverage distributions, and SLA metrics automatically.</p>
                        <div className="story-buttons">
                          <button className="button lime" onClick={triggerUpload}><Upload size={16} />Upload your data<ArrowUpRightSmall /></button>
                          <button className="button story-ghost" onClick={loadDemoData} disabled={busy}><Database size={15} />Load synthetic demo data<ArrowRight size={14} /></button>
                        </div>
                      </div>
                    </div>
                  )
                )}

                {page === 'Reports' && (
                  dataset ? (
                    <Reports dataset={dataset} onDownload={(q, n) => void exportFile(q, n)} />
                  ) : (
                    <div className="clean-hero-card">
                      <div className="clean-hero-content">
                        <div className="eyebrow light"><span className="tiny-line" /> MANAGEMENT REPORTS</div>
                        <h2>Export-ready MIS reports<br /><span>require active data.</span></h2>
                        <p>Generate PDF Operations MIS, Data Quality summaries, and Excel exception lists once your data is uploaded.</p>
                        <div className="story-buttons">
                          <button className="button lime" onClick={triggerUpload}><Upload size={16} />Upload your data<ArrowUpRightSmall /></button>
                          <button className="button story-ghost" onClick={loadDemoData} disabled={busy}><Database size={15} />Load synthetic demo data<ArrowRight size={14} /></button>
                        </div>
                      </div>
                    </div>
                  )
                )}
              </motion.div>
            </AnimatePresence>

            <footer className="app-footer">
              <span><GitBranch size={13} />OpsFlow AI<span className="footer-dot">·</span>Intelligent business operations copilot</span>
              <span>{user ? `Signed in as ${user.email} · Private isolated workspace` : 'Synthetic demo. Real workflows.'}</span>
            </footer>
          </main>
        </div>

        {notice && (
          <div className="toast" role="status">
            <CircleCheckSmall />{notice}
            <button aria-label="Dismiss notification" onClick={() => setNotice('')}><X size={15} /></button>
          </div>
        )}

        {cleanOpen && live && dataset && (
          <Cleaning
            dataset={dataset}
            column={cleanColumn}
            onClose={() => setCleanOpen(false)}
            onApplied={d => {
              queryClient.setQueryData(['dataset', datasetId], d)
              void queryClient.invalidateQueries({ queryKey: ['rows'] })
              void queryClient.invalidateQueries({ queryKey: ['audit'] })
              setSummary(undefined)
              setCleanOpen(false)
              setNotice(`Version ${d.version} created. Every approved change is in the audit trail.`)
            }}
          />
        )}

        {auditOpen && (
          <Modal title="What changed?" wide onClose={() => setAuditOpen(false)}>
            <div className="modal-body">
              <div className="inline-notice"><ShieldCheck size={16} />Every approved cell change is recorded. The original upload remains untouched.</div>
              <DataTable rows={audit.data?.items || []} columns={['version', 'row', 'column', 'old_value', 'new_value', 'rule', 'approval']} />
              {!live && <p>Load the demo and approve a cleaning preview to create an audit trail.</p>}
              {live && <button className="button secondary" onClick={() => void download(`/api/datasets/${datasetId}/original`, 'original-' + dataset?.filename).catch(fail)}>Download immutable original</button>}
            </div>
          </Modal>
        )}

        {searchOpen && (
          <Modal title="Jump to your next step" onClose={() => setSearchOpen(false)}>
            <div className="modal-body">
              <label className="search large"><Search size={19} /><input autoFocus placeholder="Find a page…" value={search} onChange={e => setSearch(e.target.value)} /></label>
              <div className="command-list">
                {navigation.filter(n => n.name.toLowerCase().includes(search.toLowerCase())).map(n => (
                  <button key={n.name} onClick={() => { navigate(n.name); setSearchOpen(false) }}>
                    <n.icon size={18} />{n.name}<ArrowRight size={16} />
                  </button>
                ))}
              </div>
            </div>
          </Modal>
        )}

        {guide && (
          <Modal title="From spreadsheet to next step" onClose={() => setGuide(false)}>
            <div className="modal-body guide">
              <p>OpsFlow AI demonstrates a safe, repeatable workflow for operational data. The facility dataset and rules are synthetic; they do not represent Grace Facility Service’s internal processes.</p>
              {[
                ['01', 'Connect', 'Upload CSV, Excel or a native PDF. Import public Google Sheets. Choose a worksheet or detected table.'],
                ['02', 'Understand', 'Review schema, quality flags, operational exceptions and automatically recommended charts.'],
                ['03', 'Review & approve', 'Inspect original and proposed cell values. Apply only selected changes to a new version.'],
                ['04', 'Ask & act', 'Ask for a chart, explore issues, prepare an MIS or download your cleaned data and audit trail.']
              ].map(([n, t, d]) => (
                <div className="guide-step" key={n}>
                  <span>{n}</span>
                  <div><h3>{t}</h3><p>{d}</p></div>
                </div>
              ))}
              <button className="button primary full" onClick={() => { setGuide(false); void demo() }}>Explore the demo<ArrowRight size={16} /></button>
            </div>
          </Modal>
        )}

        {authOpen && (
          <Modal title={user ? 'Your Account' : authMode === 'login' ? 'Sign In to OpsFlow' : 'Create an Account'} onClose={() => setAuthOpen(false)}>
            <div className="modal-body">
              {user ? (
                <div>
                  <div className="inline-notice">
                    <ShieldCheck size={18} />
                    You are signed in to a private, isolated workspace. All jobs and datasets are exclusive to your account.
                  </div>
                  <div style={{ marginTop: '20px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    <p><strong>Name:</strong> {user.name}</p>
                    <p><strong>Email:</strong> {user.email}</p>
                    <p><strong>Account ID:</strong> <code>{user.id}</code></p>
                  </div>
                  <div style={{ marginTop: '25px', display: 'flex', gap: '10px' }}>
                    <button className="button secondary full" onClick={() => void handleLogout()}>
                      <LogOut size={16} /> Sign out
                    </button>
                    <button className="button primary full" onClick={() => setAuthOpen(false)}>
                      Close
                    </button>
                  </div>
                </div>
              ) : (
                <div>
                  <div className="fast-demo-login-box">
                    <div className="fast-demo-badge"><Sparkles size={12} /> INSTANT ACCESS</div>
                    <h4>1-Click Fast Demo-Login</h4>
                    <p>Instantly launch an isolated, clean workspace. No password or registration needed.</p>
                    <button type="button" className="button lime full fast-demo-submit-btn" onClick={() => void handleDemoLogin()} disabled={authBusy}>
                      {authBusy ? <LoaderCircle className="spin" size={15} /> : <Sparkles size={15} />}
                      <span>⚡ 1-Click Demo-Login (Clean Start)</span>
                    </button>
                  </div>

                  <div className="auth-or-divider">
                    <span>OR CONTINUE WITH YOUR EMAIL</span>
                  </div>

                  <div className="auth-tabs">
                    <button type="button" className={`auth-tab ${authMode === 'login' ? 'active' : ''}`} onClick={() => { setAuthMode('login'); setAuthError('') }}>
                      Sign In
                    </button>
                    <button type="button" className={`auth-tab ${authMode === 'register' ? 'active' : ''}`} onClick={() => { setAuthMode('register'); setAuthError('') }}>
                      Create Account
                    </button>
                  </div>

                  <form className="auth-form" onSubmit={e => void handleAuth(e)}>
                    {authMode === 'register' && (
                      <div className="auth-field">
                        <label htmlFor="auth-name">Full Name</label>
                        <div className="auth-input-wrap">
                          <UserIcon size={16} />
                          <input id="auth-name" placeholder="Mehtab" value={authName} onChange={e => setAuthName(e.target.value)} required />
                        </div>
                      </div>
                    )}
                    <div className="auth-field">
                      <label htmlFor="auth-email">Email Address</label>
                      <div className="auth-input-wrap">
                        <UserIcon size={16} />
                        <input id="auth-email" type="email" placeholder="user@opsflow.ai" value={authEmail} onChange={e => setAuthEmail(e.target.value)} required />
                      </div>
                    </div>
                    <div className="auth-field">
                      <label htmlFor="auth-password">Password</label>
                      <div className="auth-input-wrap">
                        <LockKeyhole size={16} />
                        <input id="auth-password" type="password" placeholder="••••••••" value={authPassword} onChange={e => setAuthPassword(e.target.value)} required minLength={6} />
                      </div>
                    </div>

                    {authError && <div className="error-banner" role="alert">{authError}</div>}

                    <div className="auth-actions">
                      <button className="button primary full" type="submit" disabled={authBusy}>
                        {authBusy ? <LoaderCircle className="spin" size={16} /> : <Check size={16} />}
                        {authMode === 'register' ? 'Create Isolated Workspace' : 'Sign In'}
                      </button>
                      <button type="button" className="auth-guest-btn" onClick={() => setAuthOpen(false)}>
                        Continue with Demo Workspace
                      </button>
                    </div>
                  </form>
                </div>
              )}
            </div>
          </Modal>
        )}

        {cleanConfirmOpen && (
          <Modal title="Clean Workspace" onClose={() => setCleanConfirmOpen(false)}>
            <div className="modal-body">
              <div className="inline-notice">
                <Sparkles size={16} />
                Start fresh without demo data clutter. Choose how you want to clean your workspace:
              </div>
              <div className="clean-choice-grid">
                <div className="clean-choice-card">
                  <div className="choice-icon"><Layers3 size={24} /></div>
                  <h4>Start Empty Workspace</h4>
                  <p>Unload current demo dataset and switch to an empty, clean workspace ready for your own files.</p>
                  <button className="button primary full" onClick={() => void setCleanWorkspace(false)}>Start Fresh Workspace</button>
                </div>
                <div className="clean-choice-card">
                  <div className="choice-icon danger"><RotateCcw size={24} /></div>
                  <h4>Reset & Wipe Workspace Data</h4>
                  <p>Clear all uploaded jobs, datasets and chat history for this session/account to zero.</p>
                  <button className="button secondary full" onClick={() => void setCleanWorkspace(true)}>Clear All Data</button>
                </div>
              </div>
            </div>
          </Modal>
        )}

        {showWakeup && !wakeDismissed && (
          <div className="backend-wakeup-overlay" role="dialog" aria-modal="true" aria-labelledby="wakeup-title">
            <div className="backend-wakeup-card">
              <div className="wakeup-icon-glow">
                {wakeSuccess ? (
                  <Check size={26} className="wakeup-check" />
                ) : (
                  <LoaderCircle size={26} className="spin" />
                )}
              </div>
              <div className="wakeup-content">
                <div className="wakeup-badge-row">
                  <span className={`wakeup-badge ${wakeSuccess ? 'success' : ''}`}>
                    {wakeSuccess ? 'CONNECTED' : 'RENDER FREE TIER'}
                  </span>
                  <span className="wakeup-badge-dim">GRACE FACILITY PROTOTYPE</span>
                </div>
                <h3 id="wakeup-title">
                  {wakeSuccess ? 'Backend is Ready!' : 'Backend is Waking Up… Please Wait'}
                </h3>
                <p>
                  {wakeSuccess
                    ? 'Fast connection established with backend services. Launching operations engine…'
                    : 'The backend service on Render is spinning up from idle state. This takes ~25–35 seconds on the free tier. Your static frontend loaded instantly!'}
                </p>
                <div className="wakeup-progress-track">
                  <div
                    className="wakeup-progress-bar"
                    style={{
                      width: wakeSuccess
                        ? '100%'
                        : `${Math.min(95, Math.max(12, wakeSeconds * 3.4))}%`,
                    }}
                  />
                </div>
                <div className="wakeup-card-footer">
                  <span>
                    {wakeSuccess ? (
                      <span className="wakeup-ready-tag"><Check size={12} /> Ready</span>
                    ) : (
                      <>Elapsed: <b>{wakeSeconds}s</b> (boot time: ~30s)</>
                    )}
                  </span>
                  {!wakeSuccess && (
                    <button
                      type="button"
                      className="wakeup-dismiss-btn"
                      onClick={() => setWakeDismissed(true)}
                      title="Dismiss popup (backend continues waking up in background)"
                    >
                      Continue in background
                    </button>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </MotionConfig>
  )
}

function Cleaning({ dataset, column, onClose, onApplied }: { dataset: Dataset; column: string | null; onClose: () => void; onApplied: (d: Dataset) => void }) {
  const fixes = dataset.analysis.issues.filter(i => i.auto_fixable && (!column || i.column === column))
  const [selected, setSelected] = useState(new Set(fixes.map(i => i.issue_id))), [confirmed, setConfirmed] = useState(false), [pending, setPending] = useState(false), [error, setError] = useState(''), [page, setPage] = useState(1)
  async function apply() {
    setPending(true)
    try {
      onApplied(await post<Dataset>(`/api/datasets/${dataset.id}/clean`, { version: dataset.version, approved_ids: [...selected], confirmed }))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Cleaning failed. Refresh your preview.')
      setPending(false)
    }
  }
  const selectedRows = new Set(fixes.filter(i => selected.has(i.issue_id)).map(i => i.row)).size
  return (
    <Modal title="Preview & Apply Safe Corrections" wide onClose={() => { if (!pending) onClose() }}>
      <div className="modal-body">
        <div className="clean-summary">
          <div><strong>{num(selected.size)}</strong><span>selected cell fixes</span></div>
          <div><strong>{num(selectedRows)}</strong><span>records updated</span></div>
          <div><strong>0</strong><span>records deleted (100% safe)</span></div>
          <ShieldCheck size={34} />
        </div>
        <div className="inline-notice">Creating Version {dataset.version + 1}. These are routine, safe formatting fixes (like trimming spaces or standardizing dates). Missing values and ambiguous dates remain untouched for your manual review.</div>
        <div className="clean-toolbar">
          <label>
            <input type="checkbox" checked={selected.size === fixes.length && fixes.length > 0} onChange={e => { setSelected(e.target.checked ? new Set(fixes.map(i => i.issue_id)) : new Set()); setConfirmed(false) }} />
            Select all {num(fixes.length)} safe fixes
          </label>
          <span>Page {page} / {Math.max(1, Math.ceil(fixes.length / 20))}</span>
        </div>
        <div className="table-scroll clean-table">
          <table>
            <thead>
              <tr><th>Apply</th><th>Row & Column</th><th>Original Value</th><th>Cleaned Value</th><th>Why This Was Suggested</th></tr>
            </thead>
            <tbody>
              {fixes.slice((page - 1) * 20, page * 20).map((i: Issue) => (
                <tr key={i.issue_id}>
                  <td>
                    <input type="checkbox" aria-label={`Apply change record ${i.row} ${i.column}`} checked={selected.has(i.issue_id)} onChange={e => { const next = new Set(selected); if (e.target.checked) next.add(i.issue_id); else next.delete(i.issue_id); setSelected(next); setConfirmed(false) }} />
                  </td>
                  <td><b>Row #{i.row}</b><small>{human(i.column)}</small></td>
                  <td><code className="old-value">{display(i.current_value)}</code></td>
                  <td><code className="new-value">{display(i.suggested_value)}</code></td>
                  <td><span>{i.reason}</span><small>{human(i.rule)} · {Math.round(i.confidence * 100)}% verified</small></td>
                </tr>
              ))}
            </tbody>
          </table>
          {!fixes.length && <div className="empty">No safe transformations remain for this selection. Uncertain values require manual source verification.</div>}
        </div>
        <div className="pagination">
          <span>Only selected transformations will be applied.</span>
          <div>
            <button className="button secondary small" disabled={page === 1} onClick={() => setPage(page - 1)}>Previous</button>
            <button className="button secondary small" disabled={page * 20 >= fixes.length} onClick={() => setPage(page + 1)}>Next</button>
          </div>
        </div>
        {error && <div className="error-banner" role="alert">{error}</div>}
        <div className="clean-confirm">
          <label><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />I reviewed the selected changes (original data is preserved)</label>
          <p>A new version will be created. Your original data is preserved.</p>
        </div>
      </div>
      <div className="modal-footer">
        <button className="button secondary" onClick={onClose} disabled={pending}>Keep reviewing</button>
        <button className="button primary" disabled={!confirmed || !selected.size || pending} onClick={() => void apply()}>
          {pending ? <LoaderCircle className="spin" size={16} /> : <Check size={16} />}Apply {selected.size} fixes
        </button>
      </div>
    </Modal>
  )
}

function ArrowUpRightSmall() { return <ArrowRight size={13} style={{ transform: 'rotate(-35deg)' }} /> }
function ChevronRightSmall() { return <ChevronDown size={13} style={{ transform: 'rotate(-90deg)' }} /> }
function CircleCheckSmall() { return <Check size={19} /> }
