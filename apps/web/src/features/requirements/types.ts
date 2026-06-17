/** 需求侧类型 */

export interface RequirementSource {
  id: string;
  project_id: string;
  source_type: string;
  title: string;
  original_text: string;
  original_file_path: string | null;
  content_hash: string;
  created_at: string;
}

export interface SourceListResponse {
  items: RequirementSource[];
}

export interface RequirementTask {
  title: string;
  description: string;
  task_type: string;
  reason: string;
  source_quote: string | null;
}

export interface ReplicationLevel {
  level: string;
  label: string;
  supported_in_v1: boolean;
  reason: string;
  suggested_scope: string;
}

export interface RequirementPlanPayload {
  topic: string;
  experiment_type: string;
  research_subject: string;
  required_tasks: RequirementTask[];
  recommended_tasks: RequirementTask[];
  optional_tasks: RequirementTask[];
  out_of_scope_tasks: RequirementTask[];
  unknown_items: RequirementTask[];
  data_requirements: string[];
  method_requirements: string[];
  chart_requirements: string[];
  report_requirements: string[];
  presentation_requirements: string[];
  acceptance_criteria: string[];
  replication_level: ReplicationLevel | null;
}

export interface RequirementPlanResponse {
  id: string;
  project_id: string;
  source_id: string;
  status: string;
  payload: RequirementPlanPayload;
  candidate_source: string;
  created_at: string;
  updated_at: string;
  confirmed_at: string | null;
}
