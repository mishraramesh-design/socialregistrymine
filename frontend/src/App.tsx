import { Route, Routes } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import Dashboard from "./pages/Dashboard";
import Connectors from "./pages/Connectors";
import Registry from "./pages/Registry";
import DoubtRegistry from "./pages/DoubtRegistry";
import Consent from "./pages/Consent";
import Delivery from "./pages/Delivery";
import OpenG2PSync from "./pages/OpenG2PSync";

export default function App() {
  return (
    <div className="flex h-screen bg-zinc-50">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/connectors" element={<Connectors />} />
          <Route path="/registry" element={<Registry />} />
          <Route path="/doubt-registry" element={<DoubtRegistry />} />
          <Route path="/consent" element={<Consent />} />
          <Route path="/delivery" element={<Delivery />} />
          <Route path="/openg2p-sync" element={<OpenG2PSync />} />
        </Routes>
      </main>
    </div>
  );
}
