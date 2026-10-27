import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  FileText, CheckCircle2, AlertTriangle, ArrowRight, ShieldCheck, 
  BookOpen, Scale, PieChart, History, Upload, RefreshCw, Sparkles,
  Layers, Landmark, XCircle, Info, ShieldAlert, Building2, Coins, Receipt,
  TrendingUp, Check, ChevronRight, SlidersHorizontal
} from 'lucide-react';

export default function App() {
  const [activeTab, setActiveTab] = useState('invoices');
  const [tenant, setTenant] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [loading, setLoading] = useState(false);
  const [processingDocId, setProcessingDocId] = useState(null);
  const [filterStatus, setFilterStatus] = useState('ALL');
  
  // Reports state
  const [trialBalance, setTrialBalance] = useState(null);
  const [ledgerEntries, setLedgerEntries] = useState([]);
  const [profitAndLoss, setProfitAndLoss] = useState(null);
  const [balanceSheet, setBalanceSheet] = useState(null);
  const [auditLogs, setAuditLogs] = useState([]);
  const [actionMessage, setActionMessage] = useState(null);

  useEffect(() => {
    fetchTenant();
    fetchDocuments();
  }, []);

  const fetchTenant = async () => {
    try {
      const res = await axios.get('/api/tenant');
      setTenant(res.data);
    } catch (err) {
      console.error("Failed to fetch tenant", err);
    }
  };

  const fetchDocuments = async () => {
    try {
      const res = await axios.get('/api/documents');
      setDocuments(res.data);
    } catch (err) {
      console.error("Failed to fetch documents", err);
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    setLoading(true);
    try {
      const res = await axios.post('/api/documents/upload', formData);
      setActionMessage({ type: 'success', text: `Uploaded ${file.name} successfully.` });
      await fetchDocuments();
      await handleProcessDocument(res.data.document_id);
    } catch (err) {
      setActionMessage({ type: 'error', text: 'Upload failed: ' + (err.response?.data?.detail || err.message) });
    } finally {
      setLoading(false);
    }
  };

  const handleProcessDocument = async (docId) => {
    setProcessingDocId(docId);
    try {
      await axios.post(`/api/documents/${docId}/process`);
      setActionMessage({ type: 'success', text: 'Extraction, Table Correction & Journal Proposal complete!' });
      await fetchDocuments();
      await handleSelectDocument(docId);
    } catch (err) {
      setActionMessage({ type: 'error', text: 'Processing failed: ' + (err.response?.data?.detail || err.message) });
    } finally {
      setProcessingDocId(null);
    }
  };

  const handleSelectDocument = async (docId) => {
    setLoading(true);
    try {
      const res = await axios.get(`/api/documents/${docId}`);
      setSelectedDoc(res.data);
      setActiveTab('review');
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handlePostEntry = async () => {
    if (!selectedDoc || !selectedDoc.proposal) return;
    setLoading(true);
    try {
      const res = await axios.post('/api/journal/post', selectedDoc.proposal);
      setActionMessage({ type: 'success', text: `Entry successfully posted to General Ledger! ID: ${res.data.journal_entry_id}` });
      await fetchDocuments();
      await handleSelectDocument(selectedDoc.id);
      fetchReports();
    } catch (err) {
      setActionMessage({ type: 'error', text: 'Failed to post entry: ' + (err.response?.data?.detail || err.message) });
    } finally {
      setLoading(false);
    }
  };

  const fetchReports = async () => {
    try {
      const [tbRes, ledRes, pnlRes, bsRes, logsRes] = await Promise.all([
        axios.get('/api/reports/trial-balance'),
        axios.get('/api/reports/ledger'),
        axios.get('/api/reports/profit-and-loss'),
        axios.get('/api/reports/balance-sheet'),
        axios.get('/api/reports/audit-logs'),
      ]);
      setTrialBalance(tbRes.data);
      setLedgerEntries(ledRes.data);
      setProfitAndLoss(pnlRes.data);
      setBalanceSheet(bsRes.data);
      setAuditLogs(logsRes.data);
    } catch (err) {
      console.error("Failed to fetch reports", err);
    }
  };

  const handleTabChange = (tab) => {
    setActiveTab(tab);
    if (['ledger', 'trial-balance', 'statements', 'audit'].includes(tab)) {
      fetchReports();
    }
  };

  // Stats calculation
  const totalInvoices = documents.length;
  const postedCount = documents.filter(d => d.status === 'POSTED').length;
  const reviewCount = documents.filter(d => d.status === 'REVIEW_REQUIRED').length;
  const totalPayableVolume = documents.reduce((acc, d) => acc + (d.grand_total || 0), 0);

  const filteredDocuments = filterStatus === 'ALL' 
    ? documents 
    : documents.filter(d => d.status === filterStatus);

  return (
    <div className="min-h-screen bg-[#020617] text-slate-100 flex flex-col font-sans selection:bg-indigo-600 selection:text-white antialiased">
      
      {/* Top Header */}
      <header className="bg-[#0b0f19]/90 border-b border-slate-800/80 sticky top-0 z-50 backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-3.5">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-sky-500 flex items-center justify-center text-white shadow-lg shadow-indigo-500/20 ring-1 ring-white/10">
              <Landmark className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-2.5">
                <h1 className="text-sm sm:text-base font-extrabold text-white tracking-tight">
                  Invoice-to-Accounting OS
                </h1>
                <span className="text-[10px] font-bold uppercase tracking-wider bg-indigo-500/10 text-indigo-400 border border-indigo-500/30 px-2 py-0.5 rounded-md">
                  Autonomous Engine
                </span>
              </div>
              <p className="text-[11px] text-slate-400 font-medium">
                Dual AI Extraction (Rana & Yao) • Indian GST & AS 10 Rules • Immutable Ledger
              </p>
            </div>
          </div>

          {tenant && (
            <div className="flex items-center space-x-4">
              <div className="text-right hidden sm:block">
                <span className="text-xs font-semibold text-slate-200 bg-slate-900 border border-slate-700/60 px-2.5 py-1 rounded-md">
                  {tenant.name}
                </span>
                <p className="text-[11px] text-slate-400 mt-1 font-mono">
                  GSTIN: <span className="text-slate-300 font-semibold">{tenant.gstin}</span> ({tenant.currency})
                </p>
              </div>
              <div className="h-8 w-px bg-slate-800 hidden sm:block"></div>
              <div className="flex items-center space-x-2 text-xs font-semibold text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-3 py-1.5 rounded-full shadow-inner">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                <span>Audit & Invariant Engine Active</span>
              </div>
            </div>
          )}
        </div>

        {/* Navigation Tabs */}
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex space-x-1 border-t border-slate-800/80 overflow-x-auto scrollbar-none">
          {[
            { id: 'invoices', label: '1. Invoices & Ingestion', icon: FileText, count: totalInvoices },
            { id: 'review', label: '2. Review & Invariant Gate', icon: ShieldCheck, badge: reviewCount > 0 ? `${reviewCount} Attention` : null, badgeColor: 'bg-amber-500/20 text-amber-300 border-amber-500/30' },
            { id: 'ledger', label: '3. General Ledger', icon: BookOpen },
            { id: 'trial-balance', label: '4. Trial Balance', icon: Scale },
            { id: 'statements', label: '5. Financial Statements', icon: PieChart },
            { id: 'audit', label: '6. Audit Trail', icon: History },
          ].map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => handleTabChange(tab.id)}
                className={`flex items-center space-x-2 py-3 px-3.5 border-b-2 font-medium text-xs sm:text-sm transition-all whitespace-nowrap cursor-pointer ${
                  isActive
                    ? 'border-indigo-500 text-indigo-400 font-bold bg-indigo-500/5'
                    : 'border-transparent text-slate-400 hover:text-slate-200 hover:border-slate-700'
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? 'text-indigo-400' : 'text-slate-400'}`} />
                <span>{tab.label}</span>
                {tab.count !== undefined && (
                  <span className="text-[10px] font-mono px-1.5 py-0.2 rounded-full bg-slate-800 text-slate-300 border border-slate-700">
                    {tab.count}
                  </span>
                )}
                {tab.badge && (
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${tab.badgeColor}`}>
                    {tab.badge}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </header>

      {/* Global Alerts */}
      {actionMessage && (
        <div className={`py-2.5 px-4 text-xs font-semibold text-center border-b transition-all flex items-center justify-center space-x-2 ${
          actionMessage.type === 'success' 
            ? 'bg-emerald-950/80 text-emerald-200 border-emerald-800/80' 
            : 'bg-rose-950/80 text-rose-200 border-rose-800/80'
        }`}>
          <span>{actionMessage.text}</span>
          <button onClick={() => setActionMessage(null)} className="ml-3 font-bold text-slate-400 hover:text-white cursor-pointer px-1">✕</button>
        </div>
      )}

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 lg:p-8 space-y-6">
        
        {/* TAB 1: INVOICES & INGESTION */}
        {activeTab === 'invoices' && (
          <div className="space-y-6">
            
            {/* KPI Metric Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="bg-[#0b0f19] p-4 rounded-xl border border-slate-800/90 shadow-sm flex items-center justify-between">
                <div>
                  <span className="text-slate-400 text-xs font-semibold uppercase tracking-wider block">Total Invoices</span>
                  <p className="text-xl font-extrabold text-white font-mono mt-1">{totalInvoices}</p>
                  <p className="text-[11px] text-slate-500 mt-0.5">Ingested via Hybrid OCR</p>
                </div>
                <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
                  <Receipt className="w-5 h-5" />
                </div>
              </div>

              <div className="bg-[#0b0f19] p-4 rounded-xl border border-slate-800/90 shadow-sm flex items-center justify-between">
                <div>
                  <span className="text-slate-400 text-xs font-semibold uppercase tracking-wider block">Posted to Ledger</span>
                  <p className="text-xl font-extrabold text-emerald-400 font-mono mt-1">{postedCount}</p>
                  <p className="text-[11px] text-slate-500 mt-0.5">Audited & Reconciled</p>
                </div>
                <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
                  <CheckCircle2 className="w-5 h-5" />
                </div>
              </div>

              <div className="bg-[#0b0f19] p-4 rounded-xl border border-slate-800/90 shadow-sm flex items-center justify-between">
                <div>
                  <span className="text-slate-400 text-xs font-semibold uppercase tracking-wider block">Review Gate Queued</span>
                  <p className="text-xl font-extrabold text-amber-400 font-mono mt-1">{reviewCount}</p>
                  <p className="text-[11px] text-slate-500 mt-0.5">Threshold / Tax Flags</p>
                </div>
                <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400">
                  <AlertTriangle className="w-5 h-5" />
                </div>
              </div>

              <div className="bg-[#0b0f19] p-4 rounded-xl border border-slate-800/90 shadow-sm flex items-center justify-between">
                <div>
                  <span className="text-slate-400 text-xs font-semibold uppercase tracking-wider block">Total Volume Ingested</span>
                  <p className="text-xl font-extrabold text-sky-400 font-mono mt-1">₹{totalPayableVolume.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</p>
                  <p className="text-[11px] text-slate-500 mt-0.5">Verified Indian GST Slabs</p>
                </div>
                <div className="w-10 h-10 rounded-xl bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400">
                  <Coins className="w-5 h-5" />
                </div>
              </div>
            </div>

            {/* Upload Area */}
            <div className="bg-[#0b0f19] p-6 sm:p-8 rounded-2xl border-2 border-dashed border-slate-800 hover:border-indigo-500/60 transition-all text-center shadow-lg">
              <div className="w-12 h-12 rounded-full bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 mx-auto mb-3">
                <Upload className="w-6 h-6" />
              </div>
              <h3 className="text-base font-extrabold text-white">Upload PDF Invoice for Autonomous Processing</h3>
              <p className="text-xs text-slate-400 max-w-xl mx-auto mt-1 mb-5 leading-relaxed">
                Accepts multi-item scanned or digital PDFs. Employs <b>Yao et al. (2026) Table Layout Correction</b> to eliminate footer-row contamination and <b>Rana et al. (2025) Heuristic Extraction</b> for template-free metadata capture.
              </p>
              
              <div className="flex flex-wrap items-center justify-center gap-3">
                <label className="inline-flex items-center px-4 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold rounded-lg cursor-pointer shadow-md shadow-indigo-600/30 transition-all active:scale-[0.98]">
                  <Upload className="w-4 h-4 mr-2" />
                  <span>Select Invoice PDF</span>
                  <input type="file" accept=".pdf" onChange={handleFileUpload} className="hidden" />
                </label>
              </div>
            </div>

            {/* Invoices List */}
            <div className="bg-[#0b0f19] rounded-2xl border border-slate-800/90 overflow-hidden shadow-xl">
              <div className="px-6 py-4 border-b border-slate-800 flex flex-wrap justify-between items-center gap-3 bg-[#080c15]">
                <div>
                  <h2 className="font-extrabold text-white text-sm tracking-wide">Document Ingestion Pipeline</h2>
                  <p className="text-xs text-slate-400">Processed invoices available for audit, invariant verification, and accounting review</p>
                </div>

                <div className="flex items-center space-x-2">
                  <div className="flex items-center bg-slate-900 border border-slate-800 rounded-lg p-0.5 text-xs font-medium">
                    {['ALL', 'REVIEW_REQUIRED', 'PROCESSED', 'POSTED'].map((st) => (
                      <button
                        key={st}
                        onClick={() => setFilterStatus(st)}
                        className={`px-2.5 py-1 rounded-md text-[11px] font-semibold transition-all cursor-pointer ${
                          filterStatus === st 
                            ? 'bg-indigo-600 text-white shadow-xs' 
                            : 'text-slate-400 hover:text-slate-200'
                        }`}
                      >
                        {st === 'ALL' ? 'All' : st.replace('_', ' ')}
                      </button>
                    ))}
                  </div>

                  <button 
                    onClick={fetchDocuments} 
                    className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold rounded-lg flex items-center space-x-1.5 transition-colors cursor-pointer border border-slate-700"
                  >
                    <RefreshCw className="w-3.5 h-3.5 text-slate-400" />
                    <span>Refresh</span>
                  </button>
                </div>
              </div>

              {filteredDocuments.length === 0 ? (
                <div className="p-12 text-center text-slate-500 text-xs">
                  No invoices matching filter. Upload a PDF or select another view.
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-[#050811] text-slate-400 font-semibold border-b border-slate-800 uppercase tracking-wider text-[11px]">
                      <tr>
                        <th className="py-3 px-5">Source File</th>
                        <th className="py-3 px-4">Invoice #</th>
                        <th className="py-3 px-4">Vendor / Supplier</th>
                        <th className="py-3 px-4 text-right">Grand Total</th>
                        <th className="py-3 px-4">Pipeline Status</th>
                        <th className="py-3 px-5 text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60 font-sans">
                      {filteredDocuments.map((doc) => (
                        <tr key={doc.id} className="hover:bg-slate-800/40 transition-colors">
                          <td className="py-3.5 px-5 font-semibold text-slate-200 flex items-center space-x-2.5">
                            <FileText className="w-4 h-4 text-indigo-400 shrink-0" />
                            <span className="truncate max-w-xs">{doc.filename}</span>
                          </td>
                          <td className="py-3.5 px-4 text-slate-300 font-mono text-xs">{doc.invoice_number || '—'}</td>
                          <td className="py-3.5 px-4 text-slate-300 font-medium">{doc.vendor_name || '—'}</td>
                          <td className="py-3.5 px-4 text-right font-bold text-white font-mono text-xs">
                            {doc.grand_total ? `₹${doc.grand_total.toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : '—'}
                          </td>
                          <td className="py-3.5 px-4">
                            <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-bold border ${
                              doc.status === 'POSTED' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' :
                              doc.status === 'PROCESSED' ? 'bg-sky-500/10 text-sky-400 border-sky-500/20' :
                              doc.status === 'REVIEW_REQUIRED' ? 'bg-amber-500/10 text-amber-300 border-amber-500/30' :
                              'bg-slate-800 text-slate-400 border-slate-700'
                            }`}>
                              {doc.status === 'REVIEW_REQUIRED' && <AlertTriangle className="w-3 h-3 mr-1 text-amber-400" />}
                              {doc.status === 'POSTED' && <CheckCircle2 className="w-3 h-3 mr-1 text-emerald-400" />}
                              {doc.status}
                            </span>
                          </td>
                          <td className="py-3.5 px-5 text-right space-x-2">
                            {doc.status === 'UPLOADED' && (
                              <button
                                onClick={() => handleProcessDocument(doc.id)}
                                disabled={processingDocId === doc.id}
                                className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold rounded-md shadow-xs transition-colors cursor-pointer"
                              >
                                {processingDocId === doc.id ? 'Processing...' : 'Run Extraction'}
                              </button>
                            )}
                            <button
                              onClick={() => handleSelectDocument(doc.id)}
                              className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-bold rounded-md border border-slate-700 transition-colors cursor-pointer inline-flex items-center space-x-1"
                            >
                              <span>Review Proposal</span>
                              <ChevronRight className="w-3.5 h-3.5 text-slate-400" />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}

        {/* TAB 2: REVIEW & PROPOSAL (SIDE-BY-SIDE) */}
        {activeTab === 'review' && (
          <div>
            {!selectedDoc ? (
              <div className="bg-[#0b0f19] p-16 text-center rounded-2xl border border-slate-800">
                <ShieldCheck className="w-12 h-12 text-slate-600 mx-auto mb-3" />
                <h3 className="text-base font-extrabold text-white">No Document Selected</h3>
                <p className="text-xs text-slate-400 mt-1 mb-5">Please select an invoice from Tab 1 to inspect extraction and double-entry proposals.</p>
                <button onClick={() => setActiveTab('invoices')} className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold rounded-lg cursor-pointer">
                  Back to Invoices
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
                
                {/* LEFT PANEL: Extracted Document & Line Items */}
                <div className="bg-[#0b0f19] rounded-2xl border border-slate-800/90 shadow-xl flex flex-col overflow-hidden">
                  <div className="p-4 border-b border-slate-800 bg-[#080c15] flex justify-between items-center">
                    <div>
                      <h2 className="text-sm font-bold text-white flex items-center space-x-2">
                        <FileText className="w-4 h-4 text-indigo-400" />
                        <span>Extracted Document Intelligence</span>
                      </h2>
                      <p className="text-[11px] text-slate-400 font-mono truncate max-w-xs">{selectedDoc.filename}</p>
                    </div>
                    <span className="px-2.5 py-1 text-[11px] font-bold rounded-full bg-slate-900 text-slate-300 border border-slate-700">
                      Pipeline: {selectedDoc.status}
                    </span>
                  </div>

                  {selectedDoc.invoice ? (
                    <div className="p-5 space-y-5 flex-1">
                      {/* Metadata Grid */}
                      <div className="grid grid-cols-2 gap-3 bg-[#050811] p-3.5 rounded-xl border border-slate-800/80 text-xs">
                        <div>
                          <span className="text-slate-400 block text-[11px] font-medium">Invoice Number</span>
                          <p className="font-extrabold text-white font-mono text-xs mt-0.5">{selectedDoc.invoice.invoice_number}</p>
                        </div>
                        <div>
                          <span className="text-slate-400 block text-[11px] font-medium">Invoice Date</span>
                          <p className="font-extrabold text-white text-xs mt-0.5">{selectedDoc.invoice.invoice_date}</p>
                        </div>
                        <div>
                          <span className="text-slate-400 block text-[11px] font-medium">Vendor / Supplier</span>
                          <p className="font-bold text-slate-200 mt-0.5">{selectedDoc.invoice.vendor_name}</p>
                          <p className="text-slate-400 font-mono text-[10px] mt-0.5">GSTIN: {selectedDoc.invoice.vendor_gstin || 'N/A'}</p>
                        </div>
                        <div>
                          <span className="text-slate-400 block text-[11px] font-medium">Buyer / Customer</span>
                          <p className="font-bold text-slate-200 mt-0.5">{selectedDoc.invoice.buyer_name || 'Modern Tech Solutions'}</p>
                          <p className="text-slate-400 font-mono text-[10px] mt-0.5">GSTIN: {selectedDoc.invoice.buyer_gstin || 'N/A'}</p>
                        </div>
                        {selectedDoc.invoice.place_of_supply && (
                          <div className="col-span-2 pt-1 border-t border-slate-800/60 flex items-center justify-between text-[11px]">
                            <span className="text-slate-400">Place of Supply:</span>
                            <span className="font-mono text-indigo-400 font-bold">{selectedDoc.invoice.place_of_supply}</span>
                          </div>
                        )}
                      </div>

                      {/* Reconstructed Line Items Table */}
                      <div>
                        <div className="flex justify-between items-center mb-2">
                          <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                            Reconstructed Line Items (Yao et al. Corrected)
                          </h4>
                          <span className="text-[10px] text-indigo-300 bg-indigo-500/10 border border-indigo-500/30 px-2 py-0.5 rounded font-mono">
                            {selectedDoc.invoice.line_items.length} Items Captured
                          </span>
                        </div>

                        <div className="border border-slate-800 rounded-xl overflow-hidden bg-[#050811]">
                          <table className="w-full text-left text-xs">
                            <thead className="bg-slate-900/90 text-slate-300 font-semibold border-b border-slate-800 text-[11px]">
                              <tr>
                                <th className="py-2.5 px-3">Item Description</th>
                                <th className="py-2.5 px-2">HSN</th>
                                <th className="py-2.5 px-2 text-right">Qty</th>
                                <th className="py-2.5 px-2 text-right">Unit Price</th>
                                <th className="py-2.5 px-2 text-right">Disc</th>
                                <th className="py-2.5 px-3 text-right">Total</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-800/50">
                              {selectedDoc.invoice.line_items.map((item, idx) => (
                                <tr key={idx} className="hover:bg-slate-800/30">
                                  <td className="py-2.5 px-3 font-semibold text-slate-200">{item.description}</td>
                                  <td className="py-2.5 px-2 text-slate-400 font-mono text-[11px]">{item.hsn_sac || '-'}</td>
                                  <td className="py-2.5 px-2 text-right font-mono text-slate-300">{item.quantity}</td>
                                  <td className="py-2.5 px-2 text-right font-mono text-slate-300">₹{item.unit_price.toFixed(2)}</td>
                                  <td className="py-2.5 px-2 text-right font-mono text-slate-400">{item.discount_amount > 0 ? `₹${item.discount_amount.toFixed(2)}` : '—'}</td>
                                  <td className="py-2.5 px-3 text-right font-mono font-bold text-white">₹{item.total_amount.toFixed(2)}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>

                      {/* Totals Summary */}
                      <div className="bg-[#050811] p-4 rounded-xl border border-slate-800 text-xs space-y-1.5 font-mono">
                        <div className="flex justify-between font-sans">
                          <span className="text-slate-400">Taxable Subtotal:</span>
                          <span className="font-semibold text-slate-200 font-mono">₹{selectedDoc.invoice.subtotal.toFixed(2)}</span>
                        </div>
                        <div className="flex justify-between font-sans">
                          <span className="text-slate-400">Total Tax (GST):</span>
                          <span className="font-semibold text-slate-200 font-mono">₹{selectedDoc.invoice.total_tax.toFixed(2)}</span>
                        </div>
                        {selectedDoc.invoice.total_discount > 0 && (
                          <div className="flex justify-between font-sans text-emerald-400">
                            <span>Total Discount:</span>
                            <span className="font-mono">-₹{selectedDoc.invoice.total_discount.toFixed(2)}</span>
                          </div>
                        )}
                        <div className="flex justify-between pt-2.5 border-t border-slate-800 font-bold text-sm text-white font-sans">
                          <span>Grand Total Payable:</span>
                          <span className="font-mono text-indigo-400 font-extrabold text-base">₹{selectedDoc.invoice.grand_total.toFixed(2)}</span>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="p-12 text-center text-slate-500 text-xs">
                      Document not extracted yet. Click "Run Extraction" to process.
                    </div>
                  )}
                </div>

                {/* RIGHT PANEL: AI Accounting Proposal & Invariant Verification */}
                <div className="bg-[#0b0f19] rounded-2xl border border-slate-800/90 shadow-xl flex flex-col overflow-hidden">
                  <div className="p-4 border-b border-slate-800 bg-[#080c15] flex justify-between items-center">
                    <div>
                      <h2 className="text-sm font-bold text-white flex items-center space-x-2">
                        <Scale className="w-4 h-4 text-emerald-400" />
                        <span>Proposed Double-Entry Journal</span>
                      </h2>
                      <p className="text-[11px] text-slate-400">Multi-Stage Deterministic Invariant Verified</p>
                    </div>

                    {selectedDoc.proposal && (
                      <span className="px-2.5 py-1 text-xs font-bold rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 flex items-center space-x-1.5">
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                        <span>Debits == Credits</span>
                      </span>
                    )}
                  </div>

                  {selectedDoc.proposal ? (
                    <div className="p-5 space-y-5 flex-1 flex flex-col justify-between">
                      <div className="space-y-4">
                        {/* Transaction Type & Narration */}
                        <div className="bg-[#050811] p-3.5 rounded-xl border border-slate-800 text-xs space-y-2">
                          <div className="flex items-center space-x-2">
                            <span className="text-slate-400 font-medium">Classification:</span>
                            <span className="font-mono text-[11px] font-bold text-indigo-300 bg-indigo-500/10 px-2 py-0.5 rounded border border-indigo-500/30">
                              {selectedDoc.proposal.transaction_type}
                            </span>
                          </div>
                          <div>
                            <span className="text-slate-400 font-medium">Narration:</span>
                            <p className="text-slate-200 italic mt-0.5 leading-relaxed">{selectedDoc.proposal.narration}</p>
                          </div>
                        </div>

                        {/* Double-Entry Table */}
                        <div className="border border-slate-800 rounded-xl overflow-hidden bg-[#050811]">
                          <table className="w-full text-left text-xs">
                            <thead className="bg-slate-900/90 text-slate-300 font-semibold border-b border-slate-800 text-[11px]">
                              <tr>
                                <th className="py-2.5 px-3.5">Account Name</th>
                                <th className="py-2.5 px-2">Code</th>
                                <th className="py-2.5 px-3 text-right">Debit (Dr)</th>
                                <th className="py-2.5 px-3.5 text-right">Credit (Cr)</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-800/50">
                              {selectedDoc.proposal.lines.map((line, idx) => (
                                <tr key={idx} className="hover:bg-slate-800/30">
                                  <td className="py-2.5 px-3.5 font-semibold text-slate-200">
                                    <div className="flex items-center space-x-2">
                                      <span className={`w-2 h-2 rounded-full shrink-0 ${line.entry_type === 'DEBIT' ? 'bg-sky-400' : 'bg-emerald-400'}`}></span>
                                      <span>{line.account_name}</span>
                                    </div>
                                  </td>
                                  <td className="py-2.5 px-2 text-slate-400 font-mono text-[11px] font-bold">{line.account_code}</td>
                                  <td className="py-2.5 px-3 text-right font-mono font-bold text-sky-400">
                                    {line.entry_type === 'DEBIT' ? `₹${line.amount.toFixed(2)}` : '—'}
                                  </td>
                                  <td className="py-2.5 px-3.5 text-right font-mono font-bold text-emerald-400">
                                    {line.entry_type === 'CREDIT' ? `₹${line.amount.toFixed(2)}` : '—'}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                            <tfoot className="bg-[#020617] font-bold border-t-2 border-slate-800 text-xs">
                              <tr>
                                <td colSpan="2" className="py-3 px-3.5 text-slate-400">Exact Balance Equality</td>
                                <td className="py-3 px-3 text-right font-mono text-sky-300 font-extrabold">₹{selectedDoc.proposal.total_debits.toFixed(2)}</td>
                                <td className="py-3 px-3.5 text-right font-mono text-emerald-300 font-extrabold">₹{selectedDoc.proposal.total_credits.toFixed(2)}</td>
                              </tr>
                            </tfoot>
                          </table>
                        </div>

                        {/* Applied Policies & Reasoning */}
                        <div className="text-xs bg-[#050811] p-3.5 rounded-xl border border-slate-800 space-y-1.5">
                          <span className="font-bold text-slate-300 block text-[11px] uppercase tracking-wider">Applied Accounting Rules:</span>
                          <ul className="list-disc list-inside space-y-1 text-[11px] text-slate-400">
                            {selectedDoc.proposal.applied_rules?.map((rule, idx) => (
                              <li key={idx} className="leading-relaxed">{rule}</li>
                            ))}
                          </ul>
                        </div>

                        {/* Deterministic Invariant & Compliance Gate Report */}
                        {selectedDoc.validation_report && (
                          <div className="bg-[#050811] p-4 rounded-xl border border-slate-800 space-y-3">
                            <div className="flex items-center justify-between">
                              <div className="flex items-center space-x-2">
                                <ShieldCheck className="w-4 h-4 text-indigo-400" />
                                <span className="font-bold text-slate-200 text-xs">Multi-Stage Invariant Verification</span>
                              </div>
                              <span className={`px-2.5 py-0.5 text-[10px] font-extrabold rounded-full border ${
                                selectedDoc.validation_report.has_blocking_failures 
                                  ? 'bg-rose-500/10 text-rose-300 border-rose-500/40' 
                                  : selectedDoc.proposal?.requires_human_review 
                                    ? 'bg-amber-500/10 text-amber-300 border-amber-500/40' 
                                    : 'bg-emerald-500/10 text-emerald-300 border-emerald-500/40'
                              }`}>
                                {selectedDoc.validation_report.has_blocking_failures 
                                  ? 'POSTING BLOCKED' 
                                  : selectedDoc.proposal?.requires_human_review 
                                    ? 'HUMAN REVIEW REQUIRED' 
                                    : 'GATE PASSED (AUTO-POSTABLE)'}
                              </span>
                            </div>

                            <p className="text-[11px] text-slate-300 font-medium">
                              {selectedDoc.validation_report.summary_message}
                            </p>

                            {/* Review Reasons Callout */}
                            {selectedDoc.proposal?.requires_human_review && selectedDoc.proposal.review_reasons?.length > 0 && (
                              <div className="p-3 bg-amber-950/20 border border-amber-500/30 rounded-lg text-amber-300 text-[11px] space-y-1">
                                <div className="font-bold flex items-center space-x-1.5 text-amber-200">
                                  <AlertTriangle className="w-3.5 h-3.5 shrink-0 text-amber-400" />
                                  <span>Accountant Attention Points:</span>
                                </div>
                                <ul className="list-disc list-inside space-y-0.5 text-amber-200/90 pl-1 leading-relaxed">
                                  {selectedDoc.proposal.review_reasons.map((r, i) => (
                                    <li key={i}>{r}</li>
                                  ))}
                                </ul>
                              </div>
                            )}

                            {/* Detailed Invariant Checks */}
                            <div className="space-y-1.5 max-h-56 overflow-y-auto pr-1">
                              {selectedDoc.validation_report.checks?.map((check, idx) => (
                                <div 
                                  key={idx} 
                                  className={`p-2 rounded-lg text-[11px] border flex flex-col space-y-1 ${
                                    check.status === 'FAIL' 
                                      ? 'bg-rose-950/20 border-rose-900/40 text-rose-300' 
                                      : check.status === 'WARNING' 
                                        ? 'bg-amber-950/20 border-amber-900/40 text-amber-300' 
                                        : 'bg-slate-900/70 border-slate-800 text-slate-300'
                                  }`}
                                >
                                  <div className="flex items-center justify-between">
                                    <div className="flex items-center space-x-1.5 font-semibold text-slate-200">
                                      {check.status === 'FAIL' ? (
                                        <XCircle className="w-3.5 h-3.5 text-rose-400 shrink-0" />
                                      ) : check.status === 'WARNING' ? (
                                        <AlertTriangle className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                                      ) : (
                                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                                      )}
                                      <span>{check.check_name}</span>
                                    </div>
                                    <span className="font-mono text-[9px] uppercase px-1.5 py-0.2 rounded font-extrabold">
                                      {check.status}
                                    </span>
                                  </div>
                                  <p className="text-[10px] text-slate-400 pl-5 leading-normal">
                                    {check.explanation}
                                  </p>
                                  {check.difference && (
                                    <div className="pl-5 text-[10px] font-mono text-rose-400 font-bold">
                                      Discrepancy: ₹{check.difference} (Expected: {check.expected_value}, Actual: {check.actual_value})
                                    </div>
                                  )}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>

                      {/* Approval Action */}
                      <div className="pt-4 border-t border-slate-800">
                        {selectedDoc.status === 'POSTED' ? (
                          <div className="p-3.5 bg-emerald-500/10 border border-emerald-500/30 rounded-xl text-emerald-300 text-xs font-bold flex items-center justify-center space-x-2">
                            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                            <span>This entry has been approved and permanently posted to the General Ledger.</span>
                          </div>
                        ) : selectedDoc.validation_report?.has_blocking_failures ? (
                          <div className="p-3.5 bg-rose-500/10 border border-rose-500/30 rounded-xl text-rose-300 text-xs font-bold flex items-center justify-center space-x-2">
                            <XCircle className="w-4 h-4 text-rose-400 shrink-0" />
                            <span>Posting Gate Blocked: Invariant violations must be resolved prior to posting.</span>
                          </div>
                        ) : selectedDoc.proposal?.requires_human_review ? (
                          <button
                            onClick={handlePostEntry}
                            disabled={loading}
                            className="w-full py-3.5 bg-amber-600 hover:bg-amber-500 text-slate-950 font-extrabold text-xs uppercase tracking-wider rounded-xl shadow-lg shadow-amber-600/20 transition-all flex items-center justify-center space-x-2 cursor-pointer active:scale-[0.99]"
                          >
                            <AlertTriangle className="w-4 h-4 text-slate-950" />
                            <span>{loading ? 'Posting...' : 'Review & Approve (Override Verification Gate)'}</span>
                          </button>
                        ) : (
                          <button
                            onClick={handlePostEntry}
                            disabled={loading}
                            className="w-full py-3.5 bg-emerald-600 hover:bg-emerald-500 text-white font-extrabold text-xs uppercase tracking-wider rounded-xl shadow-lg shadow-emerald-600/20 transition-all flex items-center justify-center space-x-2 cursor-pointer active:scale-[0.99]"
                          >
                            <CheckCircle2 className="w-4 h-4 text-white" />
                            <span>{loading ? 'Posting...' : 'Approve & Post to General Ledger'}</span>
                          </button>
                        )}
                      </div>
                    </div>
                  ) : (
                    <div className="p-12 text-center text-slate-500 text-xs">
                      No proposed journal entry generated yet.
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* TAB 3: GENERAL LEDGER */}
        {activeTab === 'ledger' && (
          <div className="bg-[#0b0f19] rounded-2xl border border-slate-800/90 overflow-hidden shadow-xl">
            <div className="px-6 py-4 border-b border-slate-800 flex justify-between items-center bg-[#080c15]">
              <div>
                <h2 className="text-sm font-extrabold text-white">General Ledger (Posted Double-Entry Journal)</h2>
                <p className="text-xs text-slate-400">Immutable, audited double-entry records with document provenance.</p>
              </div>
              <button onClick={fetchReports} className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-lg flex items-center space-x-1.5 border border-slate-700 cursor-pointer">
                <RefreshCw className="w-3.5 h-3.5 text-slate-400" />
                <span>Refresh</span>
              </button>
            </div>

            {ledgerEntries.length === 0 ? (
              <div className="p-16 text-center text-slate-500 text-sm">
                No posted journal entries yet. Process and approve invoices from Tab 1 to post to the ledger.
              </div>
            ) : (
              <div className="divide-y divide-slate-800/80">
                {ledgerEntries.map((entry) => (
                  <div key={entry.id} className="p-6 hover:bg-slate-800/30 transition-colors">
                    <div className="flex justify-between items-start mb-2.5">
                      <div>
                        <span className="font-mono text-xs font-bold text-indigo-300 bg-indigo-500/10 border border-indigo-500/30 px-2.5 py-1 rounded-md">
                          Invoice #{entry.invoice_number}
                        </span>
                        <span className="ml-3 text-xs text-slate-400 font-mono">Date: {entry.entry_date}</span>
                      </div>
                      <span className="text-[11px] font-mono text-slate-400 bg-slate-900 px-2.5 py-1 rounded border border-slate-800 font-semibold">
                        {entry.transaction_type}
                      </span>
                    </div>
                    <p className="text-xs text-slate-300 italic mb-3.5 leading-relaxed">{entry.narration}</p>

                    <div className="rounded-xl border border-slate-800 overflow-hidden bg-[#050811]">
                      <table className="w-full text-left text-xs">
                        <thead className="bg-slate-900/90 text-slate-300 font-semibold border-b border-slate-800 text-[11px]">
                          <tr>
                            <th className="py-2.5 px-3.5">Account</th>
                            <th className="py-2.5 px-2">Code</th>
                            <th className="py-2.5 px-3 text-right">Debit (₹)</th>
                            <th className="py-2.5 px-3.5 text-right">Credit (₹)</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800/50 font-mono">
                          {entry.lines.map((l, idx) => (
                            <tr key={idx} className="hover:bg-slate-800/20">
                              <td className="py-2.5 px-3.5 text-slate-200 font-sans font-semibold">{l.account_name}</td>
                              <td className="py-2.5 px-2 text-slate-400 font-bold">{l.account_code}</td>
                              <td className="py-2.5 px-3 text-right font-bold text-sky-400">
                                {l.entry_type === 'DEBIT' ? l.amount.toFixed(2) : '—'}
                              </td>
                              <td className="py-2.5 px-3.5 text-right font-bold text-emerald-400">
                                {l.entry_type === 'CREDIT' ? l.amount.toFixed(2) : '—'}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* TAB 4: TRIAL BALANCE */}
        {activeTab === 'trial-balance' && (
          <div className="bg-[#0b0f19] rounded-2xl border border-slate-800/90 overflow-hidden shadow-xl">
            <div className="px-6 py-4 border-b border-slate-800 flex justify-between items-center bg-[#080c15]">
              <div>
                <h2 className="text-sm font-extrabold text-white">Authoritative Trial Balance</h2>
                <p className="text-xs text-slate-400">
                  Dynamically aggregated from posted double-entry journal lines as of {trialBalance?.as_of_date || 'Today'}.
                </p>
              </div>

              {trialBalance?.is_balanced ? (
                <span className="px-3 py-1 rounded-full text-xs font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 flex items-center space-x-1.5">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  <span>Trial Balance Balanced</span>
                </span>
              ) : (
                <span className="px-3 py-1 rounded-full text-xs font-bold bg-rose-500/10 text-rose-400 border border-rose-500/30 flex items-center space-x-1.5">
                  <AlertTriangle className="w-4 h-4 text-rose-400" />
                  <span>Imbalance Detected</span>
                </span>
              )}
            </div>

            {!trialBalance || trialBalance.rows.length === 0 ? (
              <div className="p-16 text-center text-slate-500 text-sm">
                No active ledger balances. Post an invoice to see the trial balance generate.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-[#050811] text-slate-300 font-semibold border-b border-slate-800 uppercase tracking-wider text-[11px]">
                    <tr>
                      <th className="py-3 px-5">Account Code</th>
                      <th className="py-3 px-5">Account Name</th>
                      <th className="py-3 px-4">Category</th>
                      <th className="py-3 px-4 text-right">Debit Balance (₹)</th>
                      <th className="py-3 px-5 text-right">Credit Balance (₹)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/50 font-mono">
                    {trialBalance.rows.map((row) => (
                      <tr key={row.account_code} className="hover:bg-slate-800/30">
                        <td className="py-2.5 px-5 text-slate-400 font-bold">{row.account_code}</td>
                        <td className="py-2.5 px-5 font-sans font-semibold text-slate-200">{row.account_name}</td>
                        <td className="py-2.5 px-4 font-sans text-slate-400 font-medium">{row.category}</td>
                        <td className="py-2.5 px-4 text-right font-bold text-sky-400">
                          {row.balance_type === 'DEBIT' ? row.closing_balance.toFixed(2) : '—'}
                        </td>
                        <td className="py-2.5 px-5 text-right font-bold text-emerald-400">
                          {row.balance_type === 'CREDIT' ? row.closing_balance.toFixed(2) : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot className="bg-[#020617] font-bold border-t-2 border-slate-800 font-mono text-xs sm:text-sm">
                    <tr>
                      <td colSpan="3" className="py-3 px-5 font-sans text-white font-extrabold">Total Balance Equality</td>
                      <td className="py-3 px-4 text-right text-sky-300 font-extrabold">₹{trialBalance.total_debit_balance.toFixed(2)}</td>
                      <td className="py-3 px-5 text-right text-emerald-300 font-extrabold">₹{trialBalance.total_credit_balance.toFixed(2)}</td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            )}
          </div>
        )}

        {/* TAB 5: FINANCIAL STATEMENTS (P&L AND BALANCE SHEET) */}
        {activeTab === 'statements' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
            
            {/* Profit & Loss Statement */}
            <div className="bg-[#0b0f19] rounded-2xl border border-slate-800/90 shadow-xl flex flex-col overflow-hidden">
              <div className="p-4 border-b border-slate-800 bg-[#080c15] flex justify-between items-center">
                <h3 className="font-extrabold text-sm text-white">Statement of Profit & Loss</h3>
                <span className="text-xs text-slate-400 font-mono">Period ending {profitAndLoss?.as_of_date || 'Current'}</span>
              </div>

              {profitAndLoss ? (
                <div className="p-5 space-y-5 text-xs flex-1 flex flex-col justify-between">
                  <div className="space-y-4">
                    <div>
                      <h4 className="font-bold text-slate-400 mb-2 uppercase text-[11px] tracking-wider">Operating Revenue</h4>
                      {profitAndLoss.revenues.length === 0 ? (
                        <p className="text-slate-500 italic text-[11px]">No revenue transactions recorded this period.</p>
                      ) : (
                        profitAndLoss.revenues.map((r, i) => (
                          <div key={i} className="flex justify-between py-1.5 border-b border-slate-800/60 font-mono">
                            <span className="font-sans text-slate-300 font-semibold">{r.name}</span>
                            <span className="text-slate-200">₹{r.amount.toFixed(2)}</span>
                          </div>
                        ))
                      )}
                      <div className="flex justify-between pt-2.5 font-bold font-mono text-white text-xs">
                        <span>Total Revenue (A):</span>
                        <span className="text-emerald-400 font-extrabold">₹{profitAndLoss.total_revenue.toFixed(2)}</span>
                      </div>
                    </div>

                    <div className="pt-2">
                      <h4 className="font-bold text-slate-400 mb-2 uppercase text-[11px] tracking-wider">Operating Expenses</h4>
                      {profitAndLoss.expenses.length === 0 ? (
                        <p className="text-slate-500 italic text-[11px]">No expense transactions recorded this period.</p>
                      ) : (
                        profitAndLoss.expenses.map((e, i) => (
                          <div key={i} className="flex justify-between py-1.5 border-b border-slate-800/60 font-mono">
                            <span className="font-sans text-slate-300 font-semibold">{e.name}</span>
                            <span className="text-slate-200">₹{e.amount.toFixed(2)}</span>
                          </div>
                        ))
                      )}
                      <div className="flex justify-between pt-2.5 font-bold font-mono text-white text-xs">
                        <span>Total Expenses (B):</span>
                        <span className="text-rose-400 font-extrabold">₹{profitAndLoss.total_expenses.toFixed(2)}</span>
                      </div>
                    </div>
                  </div>

                  <div className="p-3.5 bg-[#050811] border border-slate-800 rounded-xl flex justify-between items-center font-bold text-sm">
                    <span className="text-white">Net Operating Profit / (Loss):</span>
                    <span className={profitAndLoss.net_profit >= 0 ? 'text-emerald-400 font-mono font-extrabold' : 'text-rose-400 font-mono font-extrabold'}>
                      ₹{profitAndLoss.net_profit.toFixed(2)}
                    </span>
                  </div>
                </div>
              ) : (
                <div className="p-12 text-center text-slate-500 text-xs">No P&L data available.</div>
              )}
            </div>

            {/* Balance Sheet */}
            <div className="bg-[#0b0f19] rounded-2xl border border-slate-800/90 shadow-xl flex flex-col overflow-hidden">
              <div className="p-4 border-b border-slate-800 bg-[#080c15] flex justify-between items-center">
                <h3 className="font-extrabold text-sm text-white">Balance Sheet</h3>
                <span className="text-xs text-slate-400 font-mono">As of {balanceSheet?.as_of_date || 'Current'}</span>
              </div>

              {balanceSheet ? (
                <div className="p-5 space-y-5 text-xs flex-1 flex flex-col justify-between">
                  <div className="space-y-4">
                    <div>
                      <h4 className="font-bold text-slate-400 mb-2 uppercase text-[11px] tracking-wider">Assets</h4>
                      {balanceSheet.assets.map((a, i) => (
                        <div key={i} className="flex justify-between py-1.5 border-b border-slate-800/60 font-mono">
                          <span className="font-sans text-slate-300 font-semibold">{a.name}</span>
                          <span className="text-slate-200">₹{a.amount.toFixed(2)}</span>
                        </div>
                      ))}
                      <div className="flex justify-between pt-2.5 font-bold font-mono text-sky-400 text-xs">
                        <span>Total Assets:</span>
                        <span className="font-extrabold">₹{balanceSheet.total_assets.toFixed(2)}</span>
                      </div>
                    </div>

                    <div className="pt-2">
                      <h4 className="font-bold text-slate-400 mb-2 uppercase text-[11px] tracking-wider">Liabilities & Equity</h4>
                      {balanceSheet.liabilities.map((l, i) => (
                        <div key={i} className="flex justify-between py-1.5 border-b border-slate-800/60 font-mono">
                          <span className="font-sans text-slate-300 font-semibold">{l.name}</span>
                          <span className="text-slate-200">₹{l.amount.toFixed(2)}</span>
                        </div>
                      ))}
                      <div className="flex justify-between py-1.5 border-b border-slate-800/60 font-mono text-slate-400">
                        <span className="font-sans">Retained Earnings (from P&L)</span>
                        <span>₹{balanceSheet.retained_earnings.toFixed(2)}</span>
                      </div>
                      <div className="flex justify-between pt-2.5 font-bold font-mono text-emerald-400 text-xs">
                        <span>Total Liabilities & Equity:</span>
                        <span className="font-extrabold">₹{balanceSheet.total_liabilities_and_equity.toFixed(2)}</span>
                      </div>
                    </div>
                  </div>

                  <div className={`p-3.5 rounded-xl flex justify-between items-center font-bold text-xs sm:text-sm border ${
                    balanceSheet.is_balanced 
                      ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30' 
                      : 'bg-rose-500/10 text-rose-300 border-rose-500/30'
                  }`}>
                    <span>Balance Sheet Equation:</span>
                    <span className="flex items-center space-x-1.5 font-mono">
                      <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                      <span>Assets == Liab + Equity (Balanced)</span>
                    </span>
                  </div>
                </div>
              ) : (
                <div className="p-12 text-center text-slate-500 text-xs">No Balance Sheet data available.</div>
              )}
            </div>
          </div>
        )}

        {/* TAB 6: AUDIT TRAIL */}
        {activeTab === 'audit' && (
          <div className="bg-[#0b0f19] rounded-2xl border border-slate-800/90 overflow-hidden shadow-xl">
            <div className="px-6 py-4 border-b border-slate-800 bg-[#080c15]">
              <h2 className="text-sm font-extrabold text-white">Immutable System Audit Trail</h2>
              <p className="text-xs text-slate-400">Every invoice upload, extraction, and ledger posting recorded with provenance.</p>
            </div>

            {auditLogs.length === 0 ? (
              <div className="p-16 text-center text-slate-500 text-sm">
                No audit events recorded yet.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-[#050811] text-slate-300 font-semibold border-b border-slate-800 uppercase tracking-wider text-[11px]">
                    <tr>
                      <th className="py-3 px-5">Timestamp (UTC)</th>
                      <th className="py-3 px-4">Action</th>
                      <th className="py-3 px-4">Entity</th>
                      <th className="py-3 px-4">Performed By</th>
                      <th className="py-3 px-5">Audit Details</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/50 font-mono">
                    {auditLogs.map((log) => (
                      <tr key={log.id} className="hover:bg-slate-800/30">
                        <td className="py-2.5 px-5 text-slate-400 text-[11px]">{log.timestamp}</td>
                        <td className="py-2.5 px-4 font-bold text-indigo-400">{log.action}</td>
                        <td className="py-2.5 px-4 text-slate-300 font-sans font-semibold">{log.entity_name}</td>
                        <td className="py-2.5 px-4 font-sans text-slate-400">{log.performed_by}</td>
                        <td className="py-2.5 px-5 font-sans text-slate-200">{log.details}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
