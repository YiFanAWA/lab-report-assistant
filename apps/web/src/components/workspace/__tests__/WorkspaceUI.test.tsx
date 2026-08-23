import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import {
  Button,
  Card,
  ConfirmFooter,
  EmptyState,
  ErrorPanel,
  Field,
  JobProgress,
  LoadingState,
  StatusBadge,
} from "../WorkspaceUI";

describe("WorkspaceUI", () => {
  it("统一状态文案将技术状态映射为学生可读文本", () => {
    render(<StatusBadge status="PENDING" />);
    expect(screen.getByText("等待处理")).toBeInTheDocument();
  });

  it("统一按钮保留 disabled 和 focusable 原生行为", () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick} disabled>确认</Button>);
    const button = screen.getByRole("button", { name: "确认" });
    expect(button).toBeDisabled();
    fireEvent.click(button);
    expect(onClick).not.toHaveBeenCalled();
  });

  it("统一卡片和空状态提供稳定结构", () => {
    render(
      <Card>
        <EmptyState title="没有数据" description="先上传一个文件。" />
      </Card>,
    );
    expect(screen.getByText("没有数据")).toBeInTheDocument();
    expect(screen.getByText("先上传一个文件。")).toBeInTheDocument();
  });

  it("失败状态把错误码和任务 ID 放入技术详情", () => {
    render(
      <ErrorPanel
        message="处理失败，请检查输入。"
        code="JOB_FAILED"
        jobId="job_001"
      />,
    );
    expect(screen.getByText("需要处理")).toBeInTheDocument();
    expect(screen.getByText("技术详情")).toBeInTheDocument();
    expect(screen.getByText("错误码：JOB_FAILED")).toBeInTheDocument();
    expect(screen.getByText("任务 ID：job_001")).toBeInTheDocument();
  });

  it("任务进度统一显示运行状态和技术详情", () => {
    render(
      <JobProgress
        status="FAILED"
        label="资料解析"
        errorCode="PARSE_FAILED"
        jobId="job_002"
        errorMessage="文件无法解析"
      />,
    );
    expect(screen.getByText("资料解析：需要处理")).toBeInTheDocument();
    expect(screen.getByText("文件无法解析")).toBeInTheDocument();
    expect(screen.getByText("错误码：PARSE_FAILED")).toBeInTheDocument();
  });

  it("确认 footer 支持处理中和成功反馈", () => {
    const onConfirm = vi.fn();
    render(
      <ConfirmFooter
        actionLabel="确认任务"
        pending
        pendingLabel="确认中…"
        helper="确认前仍可修改"
        success="已保存"
        onConfirm={onConfirm}
      />,
    );
    expect(screen.getByRole("button", { name: "确认中…" })).toBeDisabled();
    expect(screen.getByText("确认前仍可修改")).toBeInTheDocument();
    expect(screen.getByText("已保存")).toBeInTheDocument();
  });

  it("Field 和 FieldError 暴露可访问错误关系的视觉结构", () => {
    render(
      <Field label="来源标题" error="请输入标题">
        <input aria-label="来源标题" />
      </Field>,
    );
    expect(screen.getByText("请输入标题")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("请输入标题");
  });

  it("加载状态提供 status 语义", () => {
    render(<LoadingState label="正在读取项目…" />);
    expect(screen.getByRole("status")).toHaveTextContent("正在读取项目…");
  });
});