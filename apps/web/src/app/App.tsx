import { Routes, Route, useNavigate } from "react-router";
import { ProjectListView } from "../routes/ProjectListView";
import { CreateProjectView } from "../routes/CreateProjectView";
import { ProjectDetailView } from "../routes/ProjectDetailView";
import { RequirementWorkspaceView } from "../routes/RequirementWorkspaceView";
import { SourcesWorkspaceView } from "../routes/SourcesWorkspaceView";
import { EvidenceWorkspaceView } from "../routes/EvidenceWorkspaceView";
import { DatasetWorkspaceView } from "../routes/DatasetWorkspaceView";
import { AnalysisWorkspaceView } from "../routes/AnalysisWorkspaceView";

export function App() {
  const navigate = useNavigate();

  return (
    <Routes>
      <Route index element={<ProjectListView />} />
      <Route
        path="projects/new"
        element={
          <CreateProjectView
            onCreated={(id: string) => {
              navigate("/projects/".concat(id));
            }}
          />
        }
      />
      <Route path="projects/:projectId" element={<ProjectDetailView />} />
      <Route path="projects/:projectId/requirements" element={<RequirementWorkspaceView />} />
      <Route path="projects/:projectId/sources" element={<SourcesWorkspaceView />} />
      <Route path="projects/:projectId/evidence" element={<EvidenceWorkspaceView />} />
      <Route path="projects/:projectId/datasets" element={<DatasetWorkspaceView />} />
      <Route path="projects/:projectId/analysis" element={<AnalysisWorkspaceView />} />
    </Routes>
  );
}
