import { Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import History from "./pages/History";
import LogEntry from "./pages/LogEntry";
import SharedReflection from "./pages/SharedReflection";

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/log" element={<LogEntry />} />
        <Route path="/history" element={<History />} />
        <Route path="/shared/:id" element={<SharedReflection />} />
      </Routes>
    </Layout>
  );
}
