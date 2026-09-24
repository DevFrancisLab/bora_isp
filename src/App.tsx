import { Navigate, Route, Routes } from 'react-router-dom';
import { DashboardLayout } from './components/layout/DashboardLayout';
import { MessagesPage, PaymentsPage, PlansPage, SettingsPage } from './pages/MorePages';
import { NetworkPage } from './pages/NetworkPage';
import { OverviewPage } from './pages/OverviewPage';
import { SubscribersPage } from './pages/SubscribersPage';
import { SupportPage } from './pages/SupportPage';

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="/dashboard" element={<DashboardLayout />}>
        <Route index element={<OverviewPage />} />
        <Route path="subscribers" element={<SubscribersPage />} />
        <Route path="support" element={<SupportPage />} />
        <Route path="network" element={<NetworkPage />} />
        <Route path="messages" element={<MessagesPage />} />
        <Route path="plans" element={<PlansPage />} />
        <Route path="payments" element={<PaymentsPage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}
