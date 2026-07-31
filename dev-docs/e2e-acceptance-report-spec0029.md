# SPEC 0029 端到端集成验收报告

**执行时间：** 2026-07-31 20:43:01
**测试数据目录：** D:\java_project\lab-report-assistant\server\data\spec0029_e2e
**CSV 文件：** gastric_health_data.csv
**PDF 文件：** gastric_reference.pdf
**Provider 配置：** requirement=local_rule, evidence=local_rule, analysis=local_rule, code=local_rule, outline=local_rule

---

[20:43:01] ## 前置检查：测试数据
[20:43:01] ✅ CSV 文件存在: gastric_health_data.csv (15607 bytes)
[20:43:01] ✅ PDF 文件存在: gastric_reference.pdf (1321 bytes)
[20:43:01] ## 前置检查：数据库
[20:43:01] ✅ 数据库表已就绪
[20:43:01] ## 步骤 1：创建项目
[20:43:01] ✅ 项目创建: id=proj_b392aa4fe87e, status=DRAFT
[20:43:01] ✅ 步骤 1 完成: DRAFT
[20:43:01] ## 步骤 2：上传要求文本 + 生成任务单 + 确认
[20:43:01]    2a. 文本来源创建: id=7a26fd22bbca
[20:43:01]    2b. 任务单生成: id=da39c6efb462, source=LOCAL_RULE
[20:43:01]    2c. 任务单确认: plan_status=CONFIRMED, project=REQUIREMENT_CONFIRMED
[20:43:01] ✅ 步骤 2 完成: REQUIREMENT_CONFIRMED
[20:43:01] ## 步骤 3：上传 PDF + 解析 + 生成证据卡片 + 确认
[20:43:01]    3a. PDF 来源创建: id=706684dd21e2, job_id=1145f38c4f90
[20:43:01]    处理任务 1145f38c4f90 (type=PARSE_DOCUMENT)...
[20:43:01]    ✅ 任务完成: status=PENDING, result={'parsed_document_id': '5ed070ae3916', 'text_length': 1309}
[20:43:01]    3c. 完成来源收集: project=SOURCES_COLLECTED
[20:43:01]    3d. 触发证据生成: job_id=71e7f6ac542c
[20:43:01]    处理任务 71e7f6ac542c (type=GENERATE_EVIDENCE)...
[20:43:01]    ✅ 任务完成: status=PENDING, result={'card_count': 10}
[20:43:01]    3f. 证据卡片数量: 10
[20:43:01]    3f. 确认了 10 张候选证据卡片
[20:43:01]    3g. 完成证据确认: project=EVIDENCE_CONFIRMED
[20:43:01] ✅ 步骤 3 完成: EVIDENCE_CONFIRMED
[20:43:01] ## 步骤 4：上传 CSV + Worker 解析（自动触发分析方案生成）
[20:43:01]    4a. 数据集创建: id=f1b3d59612b5, job_id=64ad8d858e41
[20:43:01]    处理任务 64ad8d858e41 (type=PARSE_DATASET)...
[20:43:02]    ✅ 任务完成: status=PENDING, result={'row_count': 200, 'column_count': 15, 'quality_score': 99.22, 'analysis_plan_job_id': '74ca98251ce3'}
[20:43:02]    处理任务 74ca98251ce3 (type=GENERATE_ANALYSIS_PLAN)...
[20:43:02]    ✅ 任务完成: status=PENDING, result={'plan_id': 'e2736d12d410', 'cleaning_plan_count': 13, 'analysis_plan_count': 5, 'chart_plan_count': 8}
[20:43:02]    4d. 完成数据集收集: project=DATASET_READY
[20:43:02] ✅ 步骤 4 完成: DATASET_READY
[20:43:02] ## 步骤 5：确认分析方案
[20:43:02]    5a. 分析方案: id=e2736d12d410, status=CANDIDATE
[20:43:02]    5b. 分析方案确认: status=CONFIRMED
[20:43:02]    5c. 完成分析: project=ANALYSIS_CONFIRMED
[20:43:02] ✅ 步骤 5 完成: ANALYSIS_CONFIRMED
[20:43:02] ## 步骤 6：生成代码任务 + Worker 执行
[20:43:02]    6a. 触发代码生成: job_id=872caa98bd8f
[20:43:02]    处理任务 872caa98bd8f (type=GENERATE_CODE_TASK)...
[20:43:02]    ✅ 任务完成: status=PENDING, result={'code_task_id': 'c42a86c8d0d5', 'code_length': 8212, 'code_version': 1}
[20:43:02]    6c. 代码任务: id=c42a86c8d0d5, status=CANDIDATE, code_length=8212
[20:43:02]    6c. 代码任务确认: status=CONFIRMED
[20:43:02]    6d. 触发执行: job_id=5f49422b36ea
[20:43:02]    处理任务 5f49422b36ea (type=EXECUTE_CODE_TASK)...
[20:43:09]    ✅ 任务完成: status=PENDING, result={'run_id': 'd39f1ada97d2', 'exit_code': 0, 'artifact_count': 14, 'duration_seconds': 6.901541}
[20:43:09]    6f. 执行记录: id=d39f1ada97d2, status=SUCCEEDED, exit_code=0
[20:43:09]    6f. 执行产物: 9 个图表, 5 个表格
[20:43:09]       - age_vs_WBC_散点图.png (24882 bytes)
[20:43:09]       - age_分布直方图.png (28920 bytes)
[20:43:09]       - correlation_heatmap.png (136690 bytes)
[20:43:09]    6g. 完成结果确认: project=RESULT_CONFIRMED
[20:43:09] ✅ 步骤 6 完成: RESULT_CONFIRMED
[20:43:09] ## 步骤 7：生成大纲 + 确认
[20:43:09]    7a. 触发大纲生成: job_id=55e33ccbc308
[20:43:09]    处理任务 55e33ccbc308 (type=GENERATE_OUTLINE)...
[20:43:09]    ✅ 任务完成: status=PENDING, result={'outline_id': 'ca6702a36e06', 'section_count': 6}
[20:43:09]    7c. 大纲: id=ca6702a36e06, sections=6, source_types=['REQUIREMENT', 'EVIDENCE', 'DATASET', 'ANALYSIS', 'EXECUTION', 'SUMMARY']
[20:43:09]    7d. 大纲确认: outline_status=CONFIRMED, project=OUTLINE_CONFIRMED
[20:43:09] ✅ 步骤 7 完成: OUTLINE_CONFIRMED
[20:43:09] ## 步骤 8：生成 Word + PPT + 完成项目
[20:43:09]    8a. 触发 Word 生成: job_id=7434964256d7, deliverable_id=572b63051c25
[20:43:09]    处理任务 7434964256d7 (type=GENERATE_WORD)...
[20:43:10]    ✅ 任务完成: status=PENDING, result={'deliverable_id': '572b63051c25', 'version_id': '9607f81bba22', 'version': 1, 'file_size_bytes': 332468, 'duration_seconds': 0.235336, 'template_used': False}
[20:43:10]    8c. 触发 PPT 生成: job_id=3fdde69006c9, deliverable_id=b21e462759ca
[20:43:10]    处理任务 3fdde69006c9 (type=GENERATE_PPT)...
[20:43:10]    ✅ 任务完成: status=PENDING, result={'deliverable_id': 'b21e462759ca', 'version_id': 'c5456d732341', 'version': 1, 'file_size_bytes': 334411, 'duration_seconds': 0.129955}
[20:43:10]    8e. 完成项目: project=COMPLETED
[20:43:10] ✅ 步骤 8 完成: COMPLETED
[20:43:10]    8f. Word 文件: exists=True, size=332468 bytes
[20:43:10]    8f. PPT 文件: exists=True, size=334411 bytes
[20:43:10]    8g. Word 可打开: 段落数=103
[20:43:10]    8g. PPT 可打开: 幻灯片数=8
[20:43:10] 
[20:43:10] ## 最终验证汇总
[20:43:10] 项目 ID: proj_b392aa4fe87e
[20:43:10] 最终状态: COMPLETED
[20:43:10] 状态路径: DRAFT → REQUIREMENT_CONFIRMED → SOURCES_COLLECTED → EVIDENCE_CONFIRMED → DATASET_READY → ANALYSIS_PLANNED → ANALYSIS_CONFIRMED → EXECUTING → RESULT_CONFIRMED → OUTLINE_CONFIRMED → GENERATING → COMPLETED
[20:43:10] Word 文件: word_v1.docx (332468 bytes)
[20:43:10] PPT 文件: ppt_v1.pptx (334411 bytes)
[20:43:10] 执行产物总计: 9 个图表, 5 个表格
[20:43:10] 
[20:43:10] === ✅ SPEC 0029 端到端验收全部通过 ===

---

**验收结果：** PASS
**报告生成时间：** 2026-07-31 20:43:10