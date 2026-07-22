[00:02:05] # V1.0 Worker 端到端验证日志
[00:02:05] 
[00:02:05] **执行时间：** 2026-07-23 00:02:05
[00:02:05] **Python：** d:\java_project\lab-report-assistant\server\.venv\Scripts\python.exe
[00:02:05] **工作目录：** d:\java_project\lab-report-assistant\server
[00:02:05] 
[00:02:05] ---
[00:02:05] 
[00:02:05] ## 步骤 1：确保数据库迁移到最新
[00:02:07] 退出码：0
[00:02:07] ✅ 数据库迁移成功
[00:02:07] 
[00:02:07] ## 步骤 2：执行完整端到端流程
[00:02:07] 
[00:02:07] 执行内联 Python 脚本...
[00:02:09]   [E2E] 1. 创建项目: proj_6c52304bf9fb, 状态: DRAFT
[00:02:09]   [E2E] 2. 项目推进到 RESULT_CONFIRMED
[00:02:09]   [E2E] 3. 插入模拟 ExecutionRun: run_e2e_001
[00:02:09]   [E2E] 4. 触发大纲生成: job_id=37a87df3644d, type=GENERATE_OUTLINE, status=PENDING
[00:02:09]   [E2E] 5. Worker 执行大纲生成: job status=PENDING
[00:02:09]   [E2E]    大纲 ID: 55c6007bfa48
[00:02:09]   [E2E]    章节数: 6
[00:02:09]   [E2E]    候选来源: local_rule
[00:02:09]   [E2E] 6. 确认大纲: status=CONFIRMED, project=OUTLINE_CONFIRMED
[00:02:09]   [E2E] 7. 触发 Word 生成: job_id=111543149691, deliverable_id=29d1460d89f3
[00:02:09]   [E2E] 8. Worker 执行 Word 生成: job status=PENDING
[00:02:09]   [E2E]    Word 版本: v1, status=SUCCEEDED, size=37032 bytes
[00:02:09]   [E2E] 9. 触发 PPT 生成: job_id=8afc621e1dc3, deliverable_id=b49568fd5817
[00:02:09]   [E2E] 10. Worker 执行 PPT 生成: job status=PENDING
[00:02:09]   [E2E]    PPT 版本: v1, status=SUCCEEDED, size=32231 bytes
[00:02:09]   [E2E] 11. 完成项目: status=COMPLETED
[00:02:09]   [E2E] 12. 最终验证: project.status=COMPLETED
[00:02:09]   [E2E]    Word 文件存在: True (D:\java_project\lab-report-assistant\server\data\projects\proj_6c52304bf9fb\deliverables\29d1460d89f3\word_v1.docx)
[00:02:09]   [E2E]    PPT 文件存在: True (D:\java_project\lab-report-assistant\server\data\projects\proj_6c52304bf9fb\deliverables\b49568fd5817\ppt_v1.pptx)
[00:02:09]   [E2E] 
[00:02:09]   [E2E] === ✅ 端到端验证全部通过 ===
[00:02:09]   [E2E] 项目 proj_6c52304bf9fb 从 RESULT_CONFIRMED 推进到 COMPLETED
[00:02:09]   [E2E] Word 文件: D:\java_project\lab-report-assistant\server\data\projects\proj_6c52304bf9fb\deliverables\29d1460d89f3\word_v1.docx
[00:02:09]   [E2E] PPT 文件: D:\java_project\lab-report-assistant\server\data\projects\proj_6c52304bf9fb\deliverables\b49568fd5817\ppt_v1.pptx
[00:02:09]   E2E_RESULT=PASS
[00:02:09] 
[00:02:09] ✅ Worker 端到端验证全部通过
[00:02:09] 
[00:02:09] ---
[00:02:09] 
[00:02:09] ## 验证结论
[00:02:09] 
[00:02:09] 状态机流转路径：
[00:02:09] ``
[00:02:09] RESULT_CONFIRMED
[00:02:09]   → 生成大纲候选（Worker 执行 GENERATE_OUTLINE）
[00:02:09]   → 确认大纲 → OUTLINE_CONFIRMED
[00:02:09]   → 触发 Word 生成（Worker 执行 GENERATE_WORD）→ GENERATING
[00:02:09]   → 触发 PPT 生成（Worker 执行 GENERATE_PPT）
[00:02:09]   → Word+PPT 均 SUCCEEDED → COMPLETED
[00:02:09] ```