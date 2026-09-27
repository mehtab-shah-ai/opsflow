export type Cell = string | number | boolean | null
export type Row = Record<string, Cell>
export interface Issue { issue_id: string; row: number; source_row: number; column: string; issue_type: string; severity: 'critical' | 'warning' | 'info'; current_value: Cell; suggested_value: Cell; reason: string; rule: string; confidence: number; auto_fixable: boolean }
export interface ChartSpec { id: string; type: string; title: string; subtitle: string; x: string; series: string[]; data: Row[] }
export interface Site { site: string; present: number; records: number; absent: number; required: number; available: number; gap: number; attendance_rate: number }
export interface Operations { available: boolean; sites: Site[]; trend: Row[]; attendance_rate?: number; absenteeism?: number; shift_coverage?: number; staffing_gap?: number; required_staff?: number; overtime_hours?: number; task_completion?: number; sla_compliance?: number; open_incidents?: number; duplicate_records_excluded?: number }
export interface Analysis { rows: number; columns: number; schema: {name: string; type: string; missing: number; unique: number}[]; issues: Issue[]; quality_score: number; valid_records: number; severity: Record<string, number>; categories: Record<string, number>; safe_changes: number; operations: Operations; charts: ChartSpec[]; summary: string }
export interface Dataset { id: string; job_id: string; filename: string; table_name: string; created: number; demo: boolean; version: number; quality_before: number; analysis: Analysis; warnings: string[]; duration: number }
export interface TableChoice { index: number; name: string; rows: number; columns: string[]; page: number | null; confidence: string; warnings: string[]; preview: Row[] }
export interface Job { id: string; filename: string; created: number; status: string; stage: string; progress: number; dataset_id?: string; error?: string; rows?: number; issues?: number; quality_before?: number; duration?: number; tables?: TableChoice[]; durations: Record<string, number> }
export interface Provider { configured: boolean; model: string; reachable: boolean | null; model_available: boolean | null; latency_ms: number | null; last_success: number | null; failure: string | null; circuit_open: boolean }
export interface Status { backend: string; version: string; database: string; persistence: string; uptime_seconds: number; queue: number; queue_limit: number; max_upload_mb: number; max_rows: number; providers: Record<string, Provider>; formats: string[]; vision: string }
export interface ChatMessage { role: 'user' | 'assistant'; text: string; action?: string; provider?: string; chart?: ChartSpec; items?: Row[]; download?: string; column?: string | null; timestamp?: number }
export interface Summary { text: string; provider: string; model: string | null; grounding: string; cached?: boolean }
export interface User { id: string; email: string; name: string; created?: number }
export interface AuthResponse { token: string; user: User }

