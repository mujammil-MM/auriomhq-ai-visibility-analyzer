import { Route, Routes } from 'react-router-dom';
import { Layout } from './components/Layout';
import { AuditPage } from './pages/AuditPage';
import { Landing } from './pages/Landing';
import { MethodologyPage } from './pages/MethodologyPage';
import { NotFound } from './pages/NotFound';
import { SharedReportPage } from './pages/SharedReportPage';

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/audit/:auditId" element={<AuditPage />} />
        <Route path="/r/:token" element={<SharedReportPage />} />
        <Route path="/methodology" element={<MethodologyPage />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Layout>
  );
}
