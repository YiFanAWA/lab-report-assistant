/**
 * execution api 单元测试。
 *
 * 覆盖 11 个 API 函数（7 code_tasks + 4 execution_runs）：
 * - 成功场景：验证 URL、HTTP method、请求体、响应解析
 * - 错误场景：验证非 ok 响应时抛出结构化错误
 *
 * 使用 vitest mock (globalThis as any).fetch。
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  generateCodeTask,
  listCodeTasks,
  getCodeTask,
  updateCodeTask,
  confirmCodeTask,
  rejectCodeTask,
  executeCodeTask,
  listExecutionRuns,
  getExecutionRun,
  buildArtifactDownloadUrl,
  completeExecution,
} from "../api";
import type {
  CodeTask,
  CodeTaskListResponse,
  ExecutionRun,
  ExecutionRunListResponse,
} from "../types";

const PROJECT_ID = "proj_abc123";
const BASE = "/api";

/** 构造 mock fetch 的成功响应。 */
function mockOkResponse(data: unknown): Response {
  return {
    ok: true,
    status: 200,
    statusText: "OK",
    json: () => Promise.resolve(data),
  } as Response;
}

/** 构造 mock fetch 的失败响应（含结构化错误）。 */
function mockErrorResponse(
  status: number,
  errorBody: { error?: { message?: string }; message?: string }
): Response {
  return {
    ok: false,
    status,
    statusText: "Bad Request",
    json: () => Promise.resolve(errorBody),
  } as Response;
}

beforeEach(() => {
  vi.restoreAllMocks();
});

// --- code_tasks（7 个端点） ---

describe("generateCodeTask", () => {
  it("POST /analysis/{plan_id}/code/generate — 成功返回 job_id", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(mockOkResponse({ job_id: "job_gen_001" }));

    const result = await generateCodeTask(PROJECT_ID, "plan_xyz");

    expect(fetchSpy).toHaveBeenCalledOnce();
    const [url, init] = fetchSpy.mock.calls[0];
    expect(url).toBe(
      `${BASE}/projects/${PROJECT_ID}/analysis/plan_xyz/code/generate`
    );
    expect(init?.method).toBe("POST");
    expect(result).toEqual({ job_id: "job_gen_001" });
  });

  it("非 ok 响应时抛出结构化错误", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      mockErrorResponse(400, {
        error: { message: "分析方案未确认" },
      })
    );

    await expect(generateCodeTask(PROJECT_ID, "plan_xyz")).rejects.toEqual({
      message: "分析方案未确认",
    });
  });
});

describe("listCodeTasks", () => {
  it("GET /code-tasks — 成功返回任务数组", async () => {
    const tasks: CodeTask[] = [
      {
        id: "task_001",
        project_id: PROJECT_ID,
        analysis_plan_id: "plan_001",
        dataset_id: "ds_001",
        dataset_version_id: "dv_001",
        code: "import pandas as pd",
        code_version: 1,
        status: "CANDIDATE",
        candidate_source: "LOCAL_RULE",
        created_at: "2026-07-23T00:00:00Z",
        updated_at: null,
        confirmed_at: null,
      },
    ];
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(mockOkResponse({ items: tasks } as CodeTaskListResponse));

    const result = await listCodeTasks(PROJECT_ID);

    expect(fetchSpy).toHaveBeenCalledOnce();
    expect(fetchSpy.mock.calls[0][0]).toBe(
      `${BASE}/projects/${PROJECT_ID}/code-tasks`
    );
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe("task_001");
  });

  it("GET /code-tasks?status=CANDIDATE — 支持 status 过滤", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(mockOkResponse({ items: [] } as CodeTaskListResponse));

    await listCodeTasks(PROJECT_ID, "CANDIDATE");

    expect(fetchSpy.mock.calls[0][0]).toBe(
      `${BASE}/projects/${PROJECT_ID}/code-tasks?status=CANDIDATE`
    );
  });
});

describe("getCodeTask", () => {
  it("GET /code-tasks/{task_id} — 成功返回单个任务", async () => {
    const task: CodeTask = {
      id: "task_001",
      project_id: PROJECT_ID,
      analysis_plan_id: "plan_001",
      dataset_id: "ds_001",
      dataset_version_id: "dv_001",
      code: "print('hello')",
      code_version: 2,
      status: "CONFIRMED",
      candidate_source: "LOCAL_RULE",
      created_at: "2026-07-23T00:00:00Z",
      updated_at: "2026-07-23T01:00:00Z",
      confirmed_at: "2026-07-23T02:00:00Z",
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(mockOkResponse(task));

    const result = await getCodeTask(PROJECT_ID, "task_001");

    expect(result.id).toBe("task_001");
    expect(result.code_version).toBe(2);
    expect(result.status).toBe("CONFIRMED");
  });
});

describe("updateCodeTask", () => {
  it("PUT /code-tasks/{task_id} — 发送 code 请求体", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        mockOkResponse({
          id: "task_001",
          project_id: PROJECT_ID,
          analysis_plan_id: "plan_001",
          dataset_id: "ds_001",
          dataset_version_id: "dv_001",
          code: "new code",
          code_version: 2,
          status: "CANDIDATE",
          candidate_source: "LOCAL_RULE",
          created_at: "2026-07-23T00:00:00Z",
          updated_at: "2026-07-23T01:00:00Z",
          confirmed_at: null,
        } as CodeTask)
      );

    await updateCodeTask(PROJECT_ID, "task_001", { code: "new code" });

    const [url, init] = fetchSpy.mock.calls[0];
    expect(url).toBe(`${BASE}/projects/${PROJECT_ID}/code-tasks/task_001`);
    expect(init?.method).toBe("PUT");
    expect(init?.headers).toEqual({ "Content-Type": "application/json" });
    expect(init?.body).toBe(JSON.stringify({ code: "new code" }));
  });

  it("空 code 时仍发送请求（由后端校验）", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        mockOkResponse({
          id: "task_001",
          project_id: PROJECT_ID,
          analysis_plan_id: "plan_001",
          dataset_id: "ds_001",
          dataset_version_id: "dv_001",
          code: "",
          code_version: 2,
          status: "CANDIDATE",
          candidate_source: "LOCAL_RULE",
          created_at: "2026-07-23T00:00:00Z",
          updated_at: null,
          confirmed_at: null,
        } as CodeTask)
      );

    await updateCodeTask(PROJECT_ID, "task_001", { code: "" });

    expect(fetchSpy.mock.calls[0][1]?.body).toBe(JSON.stringify({ code: "" }));
  });
});

describe("confirmCodeTask", () => {
  it("POST /code-tasks/{task_id}/confirm — 成功返回 CONFIRMED 任务", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        mockOkResponse({
          id: "task_001",
          project_id: PROJECT_ID,
          analysis_plan_id: "plan_001",
          dataset_id: "ds_001",
          dataset_version_id: "dv_001",
          code: "print(1)",
          code_version: 1,
          status: "CONFIRMED",
          candidate_source: "LOCAL_RULE",
          created_at: "2026-07-23T00:00:00Z",
          updated_at: null,
          confirmed_at: "2026-07-23T01:00:00Z",
        } as CodeTask)
      );

    const result = await confirmCodeTask(PROJECT_ID, "task_001");

    const [url, init] = fetchSpy.mock.calls[0];
    expect(url).toBe(
      `${BASE}/projects/${PROJECT_ID}/code-tasks/task_001/confirm`
    );
    expect(init?.method).toBe("POST");
    expect(result.status).toBe("CONFIRMED");
  });
});

describe("rejectCodeTask", () => {
  it("POST /code-tasks/{task_id}/reject — 成功返回 REJECTED 任务", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      mockOkResponse({
        id: "task_001",
        project_id: PROJECT_ID,
        analysis_plan_id: "plan_001",
        dataset_id: "ds_001",
        dataset_version_id: "dv_001",
        code: "print(1)",
        code_version: 1,
        status: "REJECTED",
        candidate_source: "LOCAL_RULE",
        created_at: "2026-07-23T00:00:00Z",
        updated_at: null,
        confirmed_at: null,
      } as CodeTask)
    );

    const result = await rejectCodeTask(PROJECT_ID, "task_001");

    expect(result.status).toBe("REJECTED");
  });
});

describe("executeCodeTask", () => {
  it("POST /code-tasks/{task_id}/execute — 成功返回 job_id 和 code_task_id", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        mockOkResponse({ job_id: "job_exec_001", code_task_id: "task_001" })
      );

    const result = await executeCodeTask(PROJECT_ID, "task_001");

    const [url, init] = fetchSpy.mock.calls[0];
    expect(url).toBe(
      `${BASE}/projects/${PROJECT_ID}/code-tasks/task_001/execute`
    );
    expect(init?.method).toBe("POST");
    expect(result).toEqual({ job_id: "job_exec_001", code_task_id: "task_001" });
  });

  it("非 CONFIRMED 状态时抛出后端错误", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      mockErrorResponse(400, {
        error: { message: "代码任务未确认，无法执行" },
      })
    );

    await expect(executeCodeTask(PROJECT_ID, "task_001")).rejects.toEqual({
      message: "代码任务未确认，无法执行",
    });
  });
});

// --- execution_runs（4 个端点） ---

describe("listExecutionRuns", () => {
  it("GET /execution-runs — 成功返回执行记录数组（含 artifacts）", async () => {
    const runs: ExecutionRun[] = [
      {
        id: "run_001",
        project_id: PROJECT_ID,
        code_task_id: "task_001",
        dataset_version_id: "dv_001",
        code_version: 1,
        status: "SUCCEEDED",
        stdout: "done",
        stderr: "",
        exit_code: 0,
        started_at: "2026-07-23T00:00:00Z",
        finished_at: "2026-07-23T00:00:05Z",
        duration_seconds: 5.0,
        error_code: null,
        error_message: null,
        created_at: "2026-07-23T00:00:00Z",
        artifacts: [],
      },
    ];
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        mockOkResponse({ items: runs } as ExecutionRunListResponse)
      );

    const result = await listExecutionRuns(PROJECT_ID);

    expect(fetchSpy.mock.calls[0][0]).toBe(
      `${BASE}/projects/${PROJECT_ID}/execution-runs`
    );
    expect(result).toHaveLength(1);
    expect(result[0].status).toBe("SUCCEEDED");
  });

  it("GET /execution-runs?status=RUNNING — 支持 status 过滤", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        mockOkResponse({ items: [] } as ExecutionRunListResponse)
      );

    await listExecutionRuns(PROJECT_ID, "RUNNING");

    expect(fetchSpy.mock.calls[0][0]).toBe(
      `${BASE}/projects/${PROJECT_ID}/execution-runs?status=RUNNING`
    );
  });
});

describe("getExecutionRun", () => {
  it("GET /execution-runs/{run_id} — 成功返回含 stdout/stderr 的详情", async () => {
    const run: ExecutionRun = {
      id: "run_001",
      project_id: PROJECT_ID,
      code_task_id: "task_001",
      dataset_version_id: "dv_001",
      code_version: 1,
      status: "FAILED",
      stdout: "",
      stderr: "SyntaxError: invalid syntax",
      exit_code: 1,
      started_at: "2026-07-23T00:00:00Z",
      finished_at: "2026-07-23T00:00:02Z",
      duration_seconds: 2.0,
      error_code: "EXECUTION_FAILED",
      error_message: "Python 进程退出码非零",
      created_at: "2026-07-23T00:00:00Z",
      artifacts: [],
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(mockOkResponse(run));

    const result = await getExecutionRun(PROJECT_ID, "run_001");

    expect(result.status).toBe("FAILED");
    expect(result.stderr).toBe("SyntaxError: invalid syntax");
    expect(result.exit_code).toBe(1);
  });
});

describe("buildArtifactDownloadUrl", () => {
  it("构造正确的下载 URL（含 URL 编码）", () => {
    const url = buildArtifactDownloadUrl(PROJECT_ID, "run_001", "art_abc");

    expect(url).toBe(
      `${BASE}/projects/${PROJECT_ID}/execution-runs/run_001/artifacts/art_abc`
    );
  });

  it("特殊字符在路径中被 URL 编码", () => {
    const url = buildArtifactDownloadUrl("proj with space", "run/001", "art_abc");

    expect(url).toBe(
      `${BASE}/projects/proj%20with%20space/execution-runs/run%2F001/artifacts/art_abc`
    );
  });
});

describe("completeExecution", () => {
  it("POST /execution-runs/complete — 成功返回新状态", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(mockOkResponse({ status: "RESULT_CONFIRMED" }));

    const result = await completeExecution(PROJECT_ID);

    const [url, init] = fetchSpy.mock.calls[0];
    expect(url).toBe(`${BASE}/projects/${PROJECT_ID}/execution-runs/complete`);
    expect(init?.method).toBe("POST");
    expect(result).toEqual({ status: "RESULT_CONFIRMED" });
  });

  it("无成功执行记录时抛出后端错误", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      mockErrorResponse(400, {
        error: { message: "没有成功的执行记录，无法完成结果确认" },
      })
    );

    await expect(completeExecution(PROJECT_ID)).rejects.toEqual({
      message: "没有成功的执行记录，无法完成结果确认",
    });
  });
});

// --- 通用错误处理 ---

describe("handle 错误处理通用逻辑", () => {
  it("后端返回无 error 字段时回退到顶层 message", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      mockErrorResponse(500, { message: "服务器内部错误" })
    );

    await expect(listCodeTasks(PROJECT_ID)).rejects.toEqual({
      message: "服务器内部错误",
    });
  });

  it("后端返回非 JSON 响应时回退到默认错误", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: false,
      status: 502,
      statusText: "Bad Gateway",
      json: () => Promise.reject(new Error("invalid json")),
    } as Response);

    await expect(listCodeTasks(PROJECT_ID)).rejects.toEqual({
      message: "请求失败 (502)",
    });
  });
});
