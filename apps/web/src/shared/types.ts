/** 项目合同 — 与后端 ProjectResponse 对应。 */
export interface Project {
  id: string;
  name: string;
  topic: string;
  status: string;
  created_at: string;
  updated_at: string;
}

/** 项目列表响应。 */
export interface ProjectListResponse {
  items: Project[];
}

/** 创建项目请求体。 */
export interface ProjectCreateRequest {
  name: string;
  topic: string;
}

/** 后端结构化错误。 */
export interface ApiError {
  error: {
    code: string;
    message: string;
    field: string | null;
  };
}
