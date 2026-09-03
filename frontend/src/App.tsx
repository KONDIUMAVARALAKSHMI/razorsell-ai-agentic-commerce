import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import AppShell from "./components/AppShell";
import CustomerPage from "./pages/CustomerPage";
import MerchantLoginPage, { getMerchantToken } from "./pages/MerchantLoginPage";
import MerchantDashboardShell from "./pages/MerchantDashboardShell";
import MerchantOverviewPage from "./pages/MerchantOverviewPage";
import MerchantOrdersPage from "./pages/MerchantOrdersPage";
import MerchantAuditPage from "./pages/MerchantAuditPage";
import MerchantFailureCenterPage from "./pages/MerchantFailureCenterPage";

function MerchantEntry() {
  return getMerchantToken() ? <Navigate to="/merchant/overview" replace /> : <MerchantLoginPage />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<CustomerPage />} />
          <Route path="merchant">
            <Route index element={<MerchantEntry />} />
            <Route element={<MerchantDashboardShell />}>
              <Route path="overview" element={<MerchantOverviewPage />} />
              <Route path="orders" element={<MerchantOrdersPage />} />
              <Route path="audit" element={<MerchantAuditPage />} />
              <Route path="failures" element={<MerchantFailureCenterPage />} />
            </Route>
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

