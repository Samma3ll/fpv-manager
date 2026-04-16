export type LogStatus = 'pending' | 'processing' | 'ready' | 'error'

export interface Drone {
  id: number
  name: string
  description: string | null
  frame_size: string | null
  motor_kv: number | null
  prop_size: string | null
  weight_g: number | null
  notes: string | null
  created_at: string
  updated_at: string
}

export interface DroneFormValues {
  name: string
  description: string
  frame_size: string
  motor_kv: string
  prop_size: string
  weight_g: string
  notes: string
}

export interface DroneListResponse {
  items: Drone[]
  total: number
  skip: number
  limit: number
}

export interface BlackboxLog {
  id: number
  drone_id: number
  file_name: string
  file_path: string | null
  flight_date: string | null
  duration_s: number | null
  betaflight_version: string | null
  craft_name: string | null
  pid_roll: number | null
  pid_pitch: number | null
  pid_yaw: number | null
  notes: string | null
  tags: string[]
  status: LogStatus
  error_message: string | null
  log_index: number | null
  created_at: string
}

export interface BlackboxLogListResponse {
  items: BlackboxLog[]
  total: number
  skip: number
  limit: number
}

export interface AnalysisRecord {
  module: string
  result: Record<string, unknown>
  created_at: string
}

export type AnalysesResponse = Record<string, AnalysisRecord>

export interface AxisMetrics {
  rise_time_ms?: number
  overshoot_pct?: number
  settling_time_ms?: number
  ringing?: number
  steps_analyzed?: number
  dominant_frequency_hz?: number
  noise_floor?: number
  rms_error?: number
  max_error?: number
  mean_abs_error?: number
  error?: string
  warning?: string
}