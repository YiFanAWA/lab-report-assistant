import { Routes, Route, useNavigate } from "react-router";
import { ProjectListView } from "../routes/ProjectListView";
import { CreateProjectView } from "../routes/CreateProjectView";
import { ProjectDetailView } from "../routes/ProjectDetailView";
import { RequirementWorkspaceView } from "../routes/RequirementWorkspaceView";
import { SourceEvidenceWorkspaceView } from "../routes/SourceEvidenceWorkspaceView";

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
      <Route path="projects/:projectId/sources" element={<SourceEvidenceWorkspaceView />} />
    </Routes>
  );
}
