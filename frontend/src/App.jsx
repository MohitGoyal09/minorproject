import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  FileText, CheckCircle2, AlertTriangle, ShieldCheck, 
  BookOpen, Scale, PieChart, History, Upload, RefreshCw, Landmark, XCircle,
  ChevronRight, Pencil, Save, X, Download,
  FileSpreadsheet
} from 'lucide-react';

// Empty in development so Vite proxies /api to the local backend.
// Set VITE_API_BASE_URL to the deployed backend origin on Vercel.
axios.defaults.baseURL = import.meta.env.VITE_API_BASE_URL || '';

axios.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

axios.interceptors.response.use(
  (response) => response,
  (error) => {
    const url = error.config?.url || '';
    if (error.response?.status === 401 && !url.includes('/api/auth/login')) {
      localStorage.removeItem('auth_token');
      window.location.reload();
    }
    return Promise.reject(error);
  }
);

function LoginScreen({ onSubmit, error, busy }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const submit = (event) => {
    event.preventDefault();
    onSubmit(email, password);
  };

  return (
    <div className="min-h-screen bg-[#F5F6F8] text-slate-900 flex items-center justify-center px-4 font-sans selection:bg-blue-700 selection:text-white">
      <form onSubmit={submit} className="w-full max-w-sm bg-[#FFFFFF] border border-slate-200 rounded-xl shadow-xl shadow-black/30 p-7 space-y-5">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-lg bg-slate-900 flex items-center justify-center text-white">
            <Landmark className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-sm font-semibold text-slate-900">Invoice-to-Accounting OS</h1>
            <p className="text-[11px] text-slate-500">Sign in to continue</p>
          </div>
        </div>

        <div className="space-y-3">
          <label className="block">
            <span className="text-[11px] font-medium text-slate-500">Email</span>
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
              autoComplete="username"
              className="mt-1 w-full bg-[#F7F8FA] border border-slate-200 focus:border-blue-400 rounded-lg px-3 py-2 text-xs text-slate-900 outline-none transition-colors"
            />
          </label>
          <label className="block">
            <span className="text-[11px] font-medium text-slate-500">Password</span>
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
              autoComplete="current-password"
              className="mt-1 w-full bg-[#F7F8FA] border border-slate-200 focus:border-blue-400 rounded-lg px-3 py-2 text-xs text-slate-900 outline-none transition-colors"
            />
          </label>
        </div>

        {error && (
          <div className="flex items-start space-x-2 text-[11px] text-rose-700 bg-rose-50 border border-rose-200 rounded-lg px-3 py-2">
            <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5 text-rose-700" />
            <span>{error}</span>
          </div>
        )}

        <button
          type="submit"
          disabled={busy}
          className="w-full py-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-60 text-white font-bold text-xs uppercase tracking-wider rounded-xl transition-colors cursor-pointer"
        >
          {busy ? 'Signing in...' : 'Sign in'}
        </button>

        <p className="text-[10px] text-slate-500 leading-relaxed">
          Use the credentials provided by your administrator.
        </p>
      </form>
    </div>
  );
}

function EditInput({ value, onChange, type = 'text', align = 'left' }) {
  const alignment = align === 'right' ? 'text-right' : 'text-left';
  return (
    <input
      type={type}
      value={value ?? ''}
      onChange={(event) => onChange(event.target.value)}
      className={`w-full bg-[#F7F8FA] border border-blue-300 hover:border-blue-500/70 focus:border-blue-400 focus:ring-1 focus:ring-blue-500/30 rounded-md px-2 py-1 text-xs text-slate-900 font-mono outline-none transition-colors ${alignment}`}
    />
  );
}

function ExportButtons({ report }) {
  const base = "px-2.5 py-1 text-[11px] font-bold rounded-lg border flex items-center space-x-1 cursor-pointer transition-colors";
  return (
    <div className="flex items-center space-x-1.5">
      <button
        onClick={() => window.open(`/api/reports/export/${report}?format=csv`, '_blank')}
        className={`${base} bg-slate-100 hover:bg-slate-200 text-slate-700 border-slate-200`}
        title="Download as CSV"
      >
        <Download className="w-3 h-3" />
        <span>CSV</span>
      </button>
      <button
        onClick={() => window.open(`/api/reports/export/${report}?format=xlsx`, '_blank')}
        className={`${base} bg-slate-100 hover:bg-slate-200 text-emerald-700 border-slate-200`}
        title="Download as Excel workbook"
      >
        <FileSpreadsheet className="w-3 h-3" />
        <span>Excel</span>
      </button>
    </div>
  );
}

export default function App() {
  const [activeTab, setActiveTab] = useState('invoices');
  const [tenant, setTenant] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [loading, setLoading] = useState(false);
  const [processingDocId, setProcessingDocId] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(null);
  const [filterStatus, setFilterStatus] = useState('ALL');
  
  // Reports state
  const [trialBalance, setTrialBalance] = useState(null);
  const [ledgerEntries, setLedgerEntries] = useState([]);
  const [profitAndLoss, setProfitAndLoss] = useState(null);
  const [balanceSheet, setBalanceSheet] = useState(null);
  const [auditLogs, setAuditLogs] = useState([]);
  const [actionMessage, setActionMessage] = useState(null);

  // Human correction (stage 4 review interface)
  const [editMode, setEditMode] = useState(false);
  const [draft, setDraft] = useState(null);
  const [savingCorrections, setSavingCorrections] = useState(false);

  // Authentication
  const [token, setToken] = useState(() => localStorage.getItem('auth_token'));
  const [user, setUser] = useState(null);
  const [loginError, setLoginError] = useState(null);
  const [loggingIn, setLoggingIn] = useState(false);

  useEffect(() => {
    if (!token) return;
    // Confirm the stored token is still valid before loading data.
    axios.get('/api/auth/me')
      .then((res) => {
        setUser(res.data);
        fetchTenant();
        fetchDocuments();
      })
      .catch(() => {
        localStorage.removeItem('auth_token');
        setToken(null);
      });
  }, [token]);

  const handleLogin = async (email, password) => {
    setLoggingIn(true);
    setLoginError(null);
    try {
      const res = await axios.post('/api/auth/login', { email, password });
      localStorage.setItem('auth_token', res.data.access_token);
      setUser(res.data.user);
      setToken(res.data.access_token);
    } catch (err) {
      setLoginError(err.response?.data?.detail || 'Could not sign in. Check the server is running.');
    } finally {
      setLoggingIn(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('auth_token');
    setToken(null);
    setUser(null);
    setSelectedDoc(null);
    setDocuments([]);
  };

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

  const handleFileUpload = async (event) => {
    const files = Array.from(event.target.files || []);
    event.target.value = ''; // allow re-selecting the same file
    if (files.length === 0) return;

    setLoading(true);
    setUploadProgress({ done: 0, total: files.length });
    const failed = [];
    let lastDocId = null;

    // Sequential on purpose: OCR is memory-hungry and SQLite writes are serial.
    for (const file of files) {
      try {
        const formData = new FormData();
        formData.append('file', file);
        const upload = await axios.post('/api/documents/upload', formData);
        await axios.post(`/api/documents/${upload.data.document_id}/process`);
        lastDocId = upload.data.document_id;
      } catch (err) {
        failed.push(`${file.name}: ${err.response?.data?.detail || err.message}`);
      } finally {
        setUploadProgress((current) =>
          current ? { done: current.done + 1, total: current.total } : null
        );
      }
    }

    await fetchDocuments();
    const succeeded = files.length - failed.length;
    if (failed.length === 0) {
      setActionMessage({
        type: 'success',
        text: succeeded === 1 ? `Processed ${files[0].name}` : `Processed ${succeeded} invoices`,
      });
    } else {
      setActionMessage({
        type: 'error',
        text: `${succeeded} of ${files.length} processed. Failed: ${failed.join(' | ')}`,
      });
    }

    if (lastDocId) await handleSelectDocument(lastDocId);
    setUploadProgress(null);
    setLoading(false);
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
    setEditMode(false);
    setDraft(null);
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

  const handlePostEntry = async (approveWithWarnings = false) => {
    if (!selectedDoc) return;
    setLoading(true);
    try {
      // The server rebuilds the journal from the stored invoice; we only name it.
      const res = await axios.post('/api/journal/post', {
        document_id: selectedDoc.id,
        approve_with_warnings: approveWithWarnings,
      });
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

  // --- Human correction of an extracted invoice -------------------------
  const startEditing = () => {
    if (!selectedDoc?.invoice) return;
    setDraft(JSON.parse(JSON.stringify(selectedDoc.invoice)));
    setEditMode(true);
  };

  const cancelEditing = () => {
    setEditMode(false);
    setDraft(null);
  };

  const updateDraft = (field, value) => {
    setDraft((current) => ({ ...current, [field]: value }));
  };

  const updateDraftLine = (index, field, value) => {
    setDraft((current) => ({
      ...current,
      line_items: current.line_items.map((item, idx) =>
        idx === index ? { ...item, [field]: value } : item
      ),
    }));
  };

  const handleSaveCorrections = async () => {
    if (!draft) return;
    setSavingCorrections(true);
    try {
      const payload = {
        invoice_number: draft.invoice_number,
        invoice_date: draft.invoice_date,
        due_date: draft.due_date || null,
        vendor_name: draft.vendor_name,
        vendor_gstin: draft.vendor_gstin || null,
        buyer_name: draft.buyer_name || null,
        buyer_gstin: draft.buyer_gstin || null,
        place_of_supply: draft.place_of_supply || null,
        subtotal: Number(draft.subtotal),
        total_tax: Number(draft.total_tax || 0),
        total_discount: Number(draft.total_discount || 0),
        grand_total: Number(draft.grand_total),
        line_items: draft.line_items.map((item) => ({
          description: item.description,
          hsn_sac: item.hsn_sac || null,
          quantity: Number(item.quantity || 0),
          unit_price: Number(item.unit_price || 0),
          discount_amount: Number(item.discount_amount || 0),
          tax_rate_percent: Number(item.tax_rate_percent || 0),
          total_amount: Number(item.total_amount || 0),
        })),
      };
      const res = await axios.put(`/api/documents/${selectedDoc.id}/invoice`, payload);
      setSelectedDoc(res.data);
      setEditMode(false);
      setDraft(null);
      setActionMessage({ type: 'success', text: 'Corrections saved. Journal proposal and validation re-generated.' });
      await fetchDocuments();
    } catch (err) {
      const detail = err.response?.data?.detail;
      const message = Array.isArray(detail)
        ? detail.map((d) => `${d.loc?.slice(-1)[0]}: ${d.msg}`).join('; ')
        : detail || err.message;
      setActionMessage({ type: 'error', text: 'Correction failed: ' + message });
    } finally {
      setSavingCorrections(false);
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

  if (!token) {
    return <LoginScreen onSubmit={handleLogin} error={loginError} busy={loggingIn} />;
  }

  const tabs = [
    { id: 'invoices', label: 'Invoices', icon: FileText, count: totalInvoices },
    { id: 'review', label: 'Review', icon: ShieldCheck, attention: reviewCount },
    { id: 'ledger', label: 'Ledger', icon: BookOpen },
    { id: 'trial-balance', label: 'Trial balance', icon: Scale },
    { id: 'statements', label: 'Statements', icon: PieChart },
    { id: 'audit', label: 'Audit trail', icon: History },
  ];

  const pageMeta = {
    invoices: ['Invoices', 'Upload supplier invoices and watch them clear extraction.'],
    review: ['Review', 'Check the extraction, then approve or correct the proposed entry.'],
    ledger: ['Ledger', 'Posted double-entry records, immutable once written.'],
    'trial-balance': ['Trial balance', 'Balances derived from posted journal lines.'],
    statements: ['Statements', 'Profit and loss, and the balance sheet.'],
    audit: ['Audit trail', 'Ingestions, corrections, postings, and sign-ins.'],
  };

  return (
    <div className="min-h-screen bg-[#F5F6F8] text-slate-900 flex flex-col font-sans selection:bg-blue-700 selection:text-white antialiased">
      
      <div className="flex">

        {/* Sidebar: the workflow order is the navigation */}
        <aside className="hidden lg:flex w-60 shrink-0 flex-col border-r border-slate-200 bg-white sticky top-0 h-screen">
          <div className="h-14 flex items-center gap-2.5 px-4 border-b border-slate-100">
            <div className="w-8 h-8 rounded-lg bg-slate-900 flex items-center justify-center text-white">
              <Landmark className="w-4 h-4" />
            </div>
            <div className="leading-tight">
              <p className="text-[13px] font-semibold text-slate-900">Invoice to Books</p>
              <p className="text-[10px] text-slate-500">GST double-entry</p>
            </div>
          </div>

          <nav className="flex-1 px-2 py-3 space-y-0.5">
            {tabs.map((tab, index) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => handleTabChange(tab.id)}
                  className={`w-full flex items-center gap-2.5 px-2.5 py-2 rounded-md text-[13px] transition-colors cursor-pointer ${
                    isActive
                      ? 'bg-slate-100 text-slate-900 font-semibold'
                      : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                  }`}
                >
                  <Icon className={`w-4 h-4 shrink-0 ${isActive ? 'text-blue-600' : 'text-slate-400'}`} />
                  <span className="flex-1 text-left truncate">{index + 1}. {tab.label}</span>
                  {tab.count > 0 && (
                    <span className="text-[10px] font-mono text-slate-500">{tab.count}</span>
                  )}
                  {tab.attention > 0 && (
                    <span className="text-[10px] font-semibold text-amber-700 bg-amber-50 border border-amber-200 rounded px-1.5">
                      {tab.attention}
                    </span>
                  )}
                </button>
              );
            })}
          </nav>

          <div className="border-t border-slate-100 px-4 py-3 space-y-2">
            {tenant && (
              <div className="min-w-0">
                <p className="text-[11px] font-medium text-slate-900 truncate">{tenant.name}</p>
                <p className="text-[10px] font-mono text-slate-500">{tenant.gstin}</p>
              </div>
            )}
            <div className="flex items-center justify-between gap-2">
              <span className="text-[10px] text-slate-500 truncate">{user?.email}</span>
              <button
                onClick={handleLogout}
                className="text-[10px] font-medium text-slate-600 hover:text-slate-900 cursor-pointer shrink-0"
              >
                Sign out
              </button>
            </div>
          </div>
        </aside>

        <div className="flex-1 min-w-0 flex flex-col">

          {/* Small screens keep a compact top nav */}
          <header className="lg:hidden sticky top-0 z-50 bg-white border-b border-slate-200">
            <div className="h-12 px-4 flex items-center justify-between">
              <span className="text-[13px] font-semibold text-slate-900">Invoice to Books</span>
              <button onClick={handleLogout} className="text-[11px] text-slate-600 cursor-pointer">Sign out</button>
            </div>
            <div className="flex overflow-x-auto border-t border-slate-100">
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => handleTabChange(tab.id)}
                  className={`px-3 py-2 text-[11px] whitespace-nowrap border-b-2 cursor-pointer ${
                    activeTab === tab.id
                      ? 'border-blue-600 text-slate-900 font-semibold'
                      : 'border-transparent text-slate-500'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </header>

          {/* Global Alerts */}
          {actionMessage && (
            <div className={`px-6 py-2 text-xs font-medium border-b flex items-center gap-3 ${
              actionMessage.type === 'success'
                ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                : 'bg-rose-50 text-rose-800 border-rose-200'
            }`}>
              <span className="flex-1">{actionMessage.text}</span>
              <button onClick={() => setActionMessage(null)} className="font-semibold text-slate-500 hover:text-slate-900 cursor-pointer">Dismiss</button>
            </div>
          )}

          <main className="flex-1 w-full max-w-[1360px] mx-auto px-5 sm:px-7 py-6 space-y-5">

            {/* Page header */}
            <div className="pb-4 border-b border-slate-200">
              <h1 className="text-xl font-semibold tracking-tight text-slate-900">{pageMeta[activeTab][0]}</h1>
              <p className="text-[13px] text-slate-500 mt-0.5">{pageMeta[activeTab][1]}</p>
            </div>
        
        {/* TAB 1: INVOICES & INGESTION */}
        {activeTab === 'invoices' && (
          <div className="space-y-6">
            
            {/* Summary line and the one primary action */}
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[13px] text-slate-600">
                <span><span className="font-semibold text-slate-900 tabular-nums">{totalInvoices}</span> invoices</span>
                <span className="hidden sm:block w-px h-3.5 bg-slate-200"></span>
                <span><span className="font-semibold text-slate-900 tabular-nums">{postedCount}</span> posted</span>
                <span className="hidden sm:block w-px h-3.5 bg-slate-200"></span>
                <span className={reviewCount > 0 ? 'text-amber-700 font-medium' : ''}>
                  <span className="font-semibold tabular-nums">{reviewCount}</span> awaiting review
                </span>
                <span className="hidden sm:block w-px h-3.5 bg-slate-200"></span>
                <span className="font-mono tabular-nums text-slate-700">
                  ₹{totalPayableVolume.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </span>
              </div>

              <label className={`inline-flex items-center px-3.5 py-2 text-xs font-semibold rounded-lg transition-colors ${
                uploadProgress ? 'bg-blue-400 text-white cursor-wait' : 'bg-blue-600 hover:bg-blue-500 text-white cursor-pointer active:scale-[0.99]'
              }`}>
                <Upload className="w-3.5 h-3.5 mr-2" />
                <span>
                  {uploadProgress
                    ? `Processing ${uploadProgress.done} of ${uploadProgress.total}...`
                    : 'Upload PDFs'}
                </span>
                <input
                  type="file"
                  accept=".pdf"
                  multiple
                  disabled={!!uploadProgress}
                  onChange={handleFileUpload}
                  className="hidden"
                />
              </label>
            </div>

            {/* Empty state only when there is nothing to show */}
            {documents.length === 0 && (
              <div className="border border-dashed border-slate-300 rounded-lg px-6 py-12 text-center">
                <p className="text-sm font-medium text-slate-900">No invoices yet</p>
                <p className="text-[13px] text-slate-500 mt-1.5 max-w-md mx-auto leading-relaxed">
                  Upload one or several PDFs. Digital files are read from their text layer; scans and photographs go through OCR and arrive flagged for review.
                </p>
              </div>
            )}

            {/* Invoices List */}
            <div className="bg-[#FFFFFF] rounded-xl border border-slate-200 overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-200 flex flex-wrap justify-between items-center gap-3 bg-[#FAFBFC]">
                <div className="flex items-center space-x-2">
                  <div className="flex items-center bg-slate-100 border border-slate-200 rounded-lg p-0.5 text-xs font-medium">
                    {['ALL', 'REVIEW_REQUIRED', 'PROCESSED', 'POSTED'].map((st) => (
                      <button
                        key={st}
                        onClick={() => setFilterStatus(st)}
                        className={`px-2.5 py-1 rounded-md text-[11px] font-semibold transition-all cursor-pointer ${
                          filterStatus === st 
                            ? 'bg-blue-600 text-white shadow-xs' 
                            : 'text-slate-500 hover:text-slate-800'
                        }`}
                      >
                        {st === 'ALL' ? 'All' : st.replace('_', ' ')}
                      </button>
                    ))}
                  </div>

                  <button 
                    onClick={fetchDocuments} 
                    className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-lg flex items-center space-x-1.5 transition-colors cursor-pointer border border-slate-200"
                  >
                    <RefreshCw className="w-3.5 h-3.5 text-slate-500" />
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
                    <thead className="bg-[#F7F8FA] text-slate-500 font-semibold border-b border-slate-200 uppercase tracking-wider text-[11px]">
                      <tr>
                        <th className="py-3 px-5">Source File</th>
                        <th className="py-3 px-4">Invoice #</th>
                        <th className="py-3 px-4">Vendor / Supplier</th>
                        <th className="py-3 px-4 text-right">Grand Total</th>
                        <th className="py-3 px-4">Pipeline Status</th>
                        <th className="py-3 px-5 text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100/60 font-sans">
                      {filteredDocuments.map((doc) => (
                        <tr key={doc.id} className="hover:bg-slate-100/40 transition-colors">
                          <td className="py-3.5 px-5 font-semibold text-slate-800 flex items-center space-x-2.5">
                            <FileText className="w-4 h-4 text-blue-700 shrink-0" />
                            <span className="truncate max-w-xs">{doc.filename}</span>
                          </td>
                          <td className="py-3.5 px-4 text-slate-700 font-mono text-xs">{doc.invoice_number || '—'}</td>
                          <td className="py-3.5 px-4 text-slate-700 font-medium">{doc.vendor_name || '—'}</td>
                          <td className="py-3.5 px-4 text-right font-bold text-slate-900 font-mono text-xs">
                            {doc.grand_total ? `₹${doc.grand_total.toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : '—'}
                          </td>
                          <td className="py-3.5 px-4">
                            <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-bold border ${
                              doc.status === 'POSTED' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' :
                              doc.status === 'PROCESSED' ? 'bg-blue-50 text-blue-700 border-blue-200' :
                              doc.status === 'REVIEW_REQUIRED' ? 'bg-amber-50 text-amber-700 border-amber-200' :
                              'bg-slate-100 text-slate-500 border-slate-200'
                            }`}>
                              {doc.status === 'REVIEW_REQUIRED' && <AlertTriangle className="w-3 h-3 mr-1 text-amber-700" />}
                              {doc.status === 'POSTED' && <CheckCircle2 className="w-3 h-3 mr-1 text-emerald-700" />}
                              {doc.status}
                            </span>
                          </td>
                          <td className="py-3.5 px-5 text-right space-x-2">
                            {doc.status === 'UPLOADED' && (
                              <button
                                onClick={() => handleProcessDocument(doc.id)}
                                disabled={processingDocId === doc.id}
                                className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold rounded-md shadow-xs transition-colors cursor-pointer"
                              >
                                {processingDocId === doc.id ? 'Processing...' : 'Run Extraction'}
                              </button>
                            )}
                            <button
                              onClick={() => handleSelectDocument(doc.id)}
                              className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-bold rounded-md border border-slate-200 transition-colors cursor-pointer inline-flex items-center space-x-1"
                            >
                              <span>Review Proposal</span>
                              <ChevronRight className="w-3.5 h-3.5 text-slate-500" />
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
              <div className="bg-[#FFFFFF] p-16 text-center rounded-xl border border-slate-200">
                <ShieldCheck className="w-12 h-12 text-slate-600 mx-auto mb-3" />
                <h3 className="text-base font-semibold text-slate-900">No Document Selected</h3>
                <p className="text-xs text-slate-500 mt-1 mb-5">Please select an invoice from Tab 1 to inspect extraction and double-entry proposals.</p>
                <button onClick={() => setActiveTab('invoices')} className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold rounded-lg cursor-pointer">
                  Back to Invoices
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
                
                {/* LEFT PANEL: Extracted Document & Line Items */}
                <div className="bg-[#FFFFFF] rounded-xl border border-slate-200 flex flex-col overflow-hidden">
                  <div className="p-4 border-b border-slate-200 bg-[#FAFBFC] flex justify-between items-center">
                    <div>
                      <h2 className="text-sm font-bold text-slate-900 flex items-center space-x-2">
                        <FileText className="w-4 h-4 text-blue-700" />
                        <span>Extracted invoice</span>
                      </h2>
                      <p className="text-[11px] text-slate-500 font-mono truncate max-w-xs">{selectedDoc.filename}</p>
                    </div>
                    <div className="flex items-center space-x-2">
                      {selectedDoc.invoice?.confidence && selectedDoc.invoice.confidence !== 'HIGH' && (
                        <span
                          className="px-2 py-1 text-[10px] font-semibold rounded-full bg-amber-50 text-amber-700 border border-amber-200"
                          title="Fields must be checked against the original document before posting."
                        >
                          {selectedDoc.invoice.confidence === 'LOW' ? 'LOW CONFIDENCE' : 'OCR — VERIFY'}
                        </span>
                      )}
                      <span className="px-2.5 py-1 text-[11px] font-bold rounded-full bg-slate-100 text-slate-700 border border-slate-200">
                        Pipeline: {selectedDoc.status}
                      </span>
                      {selectedDoc.invoice && selectedDoc.status !== 'POSTED' && !editMode && (
                        <button
                          onClick={startEditing}
                          className="px-2.5 py-1 text-[11px] font-bold rounded-lg bg-blue-600/20 hover:bg-blue-600/40 text-blue-700 border border-blue-300 flex items-center space-x-1 cursor-pointer transition-colors"
                        >
                          <Pencil className="w-3 h-3" />
                          <span>Correct</span>
                        </button>
                      )}
                      {editMode && (
                        <>
                          <button
                            onClick={handleSaveCorrections}
                            disabled={savingCorrections}
                            className="px-2.5 py-1 text-[11px] font-bold rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white flex items-center space-x-1 cursor-pointer disabled:opacity-60 transition-colors"
                          >
                            <Save className="w-3 h-3" />
                            <span>{savingCorrections ? 'Saving...' : 'Save & Re-validate'}</span>
                          </button>
                          <button
                            onClick={cancelEditing}
                            className="px-2.5 py-1 text-[11px] font-bold rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200 flex items-center space-x-1 cursor-pointer transition-colors"
                          >
                            <X className="w-3 h-3" />
                            <span>Cancel</span>
                          </button>
                        </>
                      )}
                    </div>
                  </div>

                  {selectedDoc.invoice ? (
                    <div className="p-5 space-y-5 flex-1 flex flex-col">
                      {/* Metadata Grid */}
                      <div className="grid grid-cols-2 gap-4 text-xs">
                        <div>
                          <span className="text-slate-500 block text-[11px] font-medium">Invoice Number</span>
                          {editMode ? (
                            <div className="mt-1"><EditInput value={draft.invoice_number} onChange={(v) => updateDraft('invoice_number', v)} /></div>
                          ) : (
                            <p className="font-semibold text-slate-900 font-mono text-xs mt-0.5">{selectedDoc.invoice.invoice_number}</p>
                          )}
                        </div>
                        <div>
                          <span className="text-slate-500 block text-[11px] font-medium">Invoice Date</span>
                          {editMode ? (
                            <div className="mt-1"><EditInput type="date" value={draft.invoice_date} onChange={(v) => updateDraft('invoice_date', v)} /></div>
                          ) : (
                            <p className="font-semibold text-slate-900 text-xs mt-0.5">{selectedDoc.invoice.invoice_date}</p>
                          )}
                        </div>
                        <div>
                          <span className="text-slate-500 block text-[11px] font-medium">Vendor / Supplier</span>
                          {editMode ? (
                            <div className="space-y-1 mt-1">
                              <EditInput value={draft.vendor_name} onChange={(v) => updateDraft('vendor_name', v)} />
                              <EditInput value={draft.vendor_gstin} onChange={(v) => updateDraft('vendor_gstin', v)} />
                            </div>
                          ) : (
                            <>
                              <p className="font-bold text-slate-800 mt-0.5">{selectedDoc.invoice.vendor_name}</p>
                              <p className="text-slate-500 font-mono text-[10px] mt-0.5">GSTIN: {selectedDoc.invoice.vendor_gstin || 'N/A'}</p>
                            </>
                          )}
                        </div>
                        <div>
                          <span className="text-slate-500 block text-[11px] font-medium">Buyer / Customer</span>
                          {editMode ? (
                            <div className="space-y-1 mt-1">
                              <EditInput value={draft.buyer_name} onChange={(v) => updateDraft('buyer_name', v)} />
                              <EditInput value={draft.buyer_gstin} onChange={(v) => updateDraft('buyer_gstin', v)} />
                            </div>
                          ) : (
                            <>
                              <p className="font-bold text-slate-800 mt-0.5">{selectedDoc.invoice.buyer_name || 'Modern Tech Solutions'}</p>
                              <p className="text-slate-500 font-mono text-[10px] mt-0.5">GSTIN: {selectedDoc.invoice.buyer_gstin || 'N/A'}</p>
                            </>
                          )}
                        </div>
                        {editMode ? (
                          <div className="col-span-2 pt-1 border-t border-slate-200 grid grid-cols-2 gap-3">
                            <div>
                              <span className="text-slate-500 block text-[11px] font-medium">Due Date</span>
                              <div className="mt-1"><EditInput type="date" value={draft.due_date} onChange={(v) => updateDraft('due_date', v)} /></div>
                            </div>
                            <div>
                              <span className="text-slate-500 block text-[11px] font-medium">Place of Supply</span>
                              <div className="mt-1"><EditInput value={draft.place_of_supply} onChange={(v) => updateDraft('place_of_supply', v)} /></div>
                            </div>
                          </div>
                        ) : (
                          (selectedDoc.invoice.place_of_supply || selectedDoc.invoice.due_date) && (
                            <div className="col-span-2 pt-1 border-t border-slate-200 flex items-center justify-between text-[11px]">
                              <span className="text-slate-500">Place of Supply: <span className="font-mono text-blue-700 font-bold">{selectedDoc.invoice.place_of_supply || 'N/A'}</span></span>
                              <span className="text-slate-500">Due: <span className="font-mono text-slate-700">{selectedDoc.invoice.due_date || 'N/A'}</span></span>
                            </div>
                          )
                        )}
                      </div>

                      {/* Reconstructed Line Items Table */}
                      <div>
                        <div className="flex justify-between items-center mb-2">
                          <h4 className="text-xs font-semibold text-slate-900">
                            Line items
                          </h4>
                          <span className="text-[10px] text-blue-700 bg-blue-50 border border-blue-200 px-2 py-0.5 rounded font-mono">
                            {selectedDoc.invoice.line_items.length} items
                          </span>
                        </div>

                        <div className="border-y border-slate-200">
                          <table className="w-full text-left text-xs">
                            <thead className="bg-slate-50 text-slate-700 font-semibold border-b border-slate-200 text-[11px]">
                              <tr>
                                <th className="py-2.5 px-3">Item Description</th>
                                <th className="py-2.5 px-2">HSN</th>
                                <th className="py-2.5 px-2 text-right">Qty</th>
                                <th className="py-2.5 px-2 text-right">Unit Price</th>
                                <th className="py-2.5 px-2 text-right">Disc</th>
                                <th className="py-2.5 px-3 text-right">Total</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100">
                              {(editMode ? draft.line_items : selectedDoc.invoice.line_items).map((item, idx) => (
                                <tr key={idx} className="hover:bg-slate-50">
                                  <td className="py-2.5 px-3 font-semibold text-slate-800">
                                    {editMode
                                      ? <EditInput value={item.description} onChange={(v) => updateDraftLine(idx, 'description', v)} />
                                      : item.description}
                                  </td>
                                  <td className="py-2.5 px-2 text-slate-500 font-mono text-[11px]">
                                    {editMode
                                      ? <EditInput value={item.hsn_sac} onChange={(v) => updateDraftLine(idx, 'hsn_sac', v)} />
                                      : (item.hsn_sac || '-')}
                                  </td>
                                  <td className="py-2.5 px-2 text-right font-mono text-slate-700">
                                    {editMode
                                      ? <EditInput value={item.quantity} align="right" onChange={(v) => updateDraftLine(idx, 'quantity', v)} />
                                      : item.quantity}
                                  </td>
                                  <td className="py-2.5 px-2 text-right font-mono text-slate-700">
                                    {editMode
                                      ? <EditInput value={item.unit_price} align="right" onChange={(v) => updateDraftLine(idx, 'unit_price', v)} />
                                      : `₹${item.unit_price.toFixed(2)}`}
                                  </td>
                                  <td className="py-2.5 px-2 text-right font-mono text-slate-500">
                                    {editMode
                                      ? <EditInput value={item.discount_amount} align="right" onChange={(v) => updateDraftLine(idx, 'discount_amount', v)} />
                                      : (item.discount_amount > 0 ? `₹${item.discount_amount.toFixed(2)}` : '—')}
                                  </td>
                                  <td className="py-2.5 px-3 text-right font-mono font-bold text-slate-900">
                                    {editMode
                                      ? <EditInput value={item.total_amount} align="right" onChange={(v) => updateDraftLine(idx, 'total_amount', v)} />
                                      : `₹${item.total_amount.toFixed(2)}`}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>

                      {/* Totals Summary */}
                      <div className="border-t border-slate-200 pt-4 text-xs space-y-1.5 font-mono">
                        <div className="flex justify-between items-center font-sans gap-3">
                          <span className="text-slate-500">Taxable Subtotal:</span>
                          {editMode
                            ? <div className="w-32"><EditInput value={draft.subtotal} align="right" onChange={(v) => updateDraft('subtotal', v)} /></div>
                            : <span className="font-semibold text-slate-800 font-mono">₹{selectedDoc.invoice.subtotal.toFixed(2)}</span>}
                        </div>
                        <div className="flex justify-between items-center font-sans gap-3">
                          <span className="text-slate-500">Total Tax (GST):</span>
                          {editMode
                            ? <div className="w-32"><EditInput value={draft.total_tax} align="right" onChange={(v) => updateDraft('total_tax', v)} /></div>
                            : <span className="font-semibold text-slate-800 font-mono">₹{selectedDoc.invoice.total_tax.toFixed(2)}</span>}
                        </div>
                        <div className="flex justify-between items-center font-sans text-emerald-700 gap-3">
                          <span>Total Discount:</span>
                          {editMode
                            ? <div className="w-32"><EditInput value={draft.total_discount} align="right" onChange={(v) => updateDraft('total_discount', v)} /></div>
                            : <span className="font-mono">-₹{selectedDoc.invoice.total_discount.toFixed(2)}</span>}
                        </div>
                        <div className="flex justify-between items-center pt-2.5 border-t border-slate-200 font-bold text-sm text-slate-900 font-sans gap-3">
                          <span>Grand Total Payable:</span>
                          {editMode
                            ? <div className="w-32"><EditInput value={draft.grand_total} align="right" onChange={(v) => updateDraft('grand_total', v)} /></div>
                            : <span className="font-mono text-blue-700 font-semibold text-base">₹{selectedDoc.invoice.grand_total.toFixed(2)}</span>}
                        </div>
                        {editMode && (
                          <p className="text-[10px] text-amber-700/90 pt-1.5 border-t border-slate-200 leading-relaxed">
                            Sum of line totals: ₹{draft.line_items.reduce((acc, item) => acc + (Number(item.total_amount) || 0), 0).toFixed(2)}.
                            Keep the totals consistent, or validation will block posting.
                          </p>
                        )}
                      </div>

                      {/* Deterministic Invariant & Compliance Gate Report */}
                      {selectedDoc.validation_report && (
                        <div className="border-t border-slate-200 pt-4 space-y-3">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center space-x-2">
                              <ShieldCheck className="w-4 h-4 text-blue-700" />
                              <span className="font-semibold text-slate-900 text-xs">Checks</span>
                            </div>
                            <span className={`px-2.5 py-0.5 text-[10px] font-semibold rounded-full border ${
                              selectedDoc.validation_report.has_blocking_failures 
                                ? 'bg-rose-50 text-rose-700 border-rose-300' 
                                : selectedDoc.proposal?.requires_human_review 
                                  ? 'bg-amber-50 text-amber-700 border-amber-300' 
                                  : 'bg-emerald-50 text-emerald-700 border-emerald-500/40'
                            }`}>
                              {selectedDoc.validation_report.has_blocking_failures 
                                ? 'POSTING BLOCKED' 
                                : selectedDoc.proposal?.requires_human_review 
                                  ? 'HUMAN REVIEW REQUIRED' 
                                  : 'GATE PASSED (AUTO-POSTABLE)'}
                            </span>
                          </div>

                          <p className="text-[11px] text-slate-700 font-medium">
                            {selectedDoc.validation_report.summary_message}
                          </p>

                          {/* Review Reasons Callout */}
                          {selectedDoc.proposal?.requires_human_review && selectedDoc.proposal.review_reasons?.length > 0 && (
                            <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-amber-700 text-[11px] space-y-1">
                              <div className="font-bold flex items-center space-x-1.5 text-amber-800">
                                <AlertTriangle className="w-3.5 h-3.5 shrink-0 text-amber-700" />
                                <span>Needs attention:</span>
                              </div>
                              <ul className="list-disc list-inside space-y-0.5 text-amber-800 pl-1 leading-relaxed">
                                {selectedDoc.proposal.review_reasons.map((r, i) => (
                                  <li key={i}>{r}</li>
                                ))}
                              </ul>
                            </div>
                          )}

                          {/* Detailed Invariant Checks */}
                          <div className="divide-y divide-slate-100">
                            {selectedDoc.validation_report.checks?.map((check, idx) => (
                              <div 
                                key={idx} 
                                className={`py-2.5 text-[11px] flex flex-col gap-1 ${
                                  check.status === 'FAIL'
                                    ? 'text-rose-700'
                                    : check.status === 'WARNING'
                                      ? 'text-amber-700'
                                      : 'text-slate-700'
                                }`}
                              >
                                <div className="flex items-center justify-between">
                                  <div className="flex items-center space-x-1.5 font-semibold text-slate-800">
                                    {check.status === 'FAIL' ? (
                                      <XCircle className="w-3.5 h-3.5 text-rose-700 shrink-0" />
                                    ) : check.status === 'WARNING' ? (
                                      <AlertTriangle className="w-3.5 h-3.5 text-amber-700 shrink-0" />
                                    ) : (
                                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-700 shrink-0" />
                                    )}
                                    <span>{check.check_name}</span>
                                  </div>
                                  <span className="font-mono text-[9px] uppercase px-1.5 py-0.2 rounded font-semibold">
                                    {check.status}
                                  </span>
                                </div>
                                <p className="text-[10px] text-slate-500 pl-5 leading-normal">
                                  {check.explanation}
                                </p>
                                {check.difference && (
                                  <div className="pl-5 text-[10px] font-mono text-rose-700 font-bold">
                                    Discrepancy: ₹{check.difference} (Expected: {check.expected_value}, Actual: {check.actual_value})
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="p-12 text-center text-slate-500 text-xs">
                      Document not extracted yet. Click "Run Extraction" to process.
                    </div>
                  )}
                </div>

                {/* RIGHT PANEL: AI Accounting Proposal & Invariant Verification */}
                <div className="bg-[#FFFFFF] rounded-xl border border-slate-200 flex flex-col overflow-hidden">
                  <div className="p-4 border-b border-slate-200 bg-[#FAFBFC] flex justify-between items-center">
                    <div>
                      <h2 className="text-sm font-bold text-slate-900 flex items-center space-x-2">
                        <Scale className="w-4 h-4 text-emerald-700" />
                        <span>Journal entry</span>
                      </h2>
                      <p className="text-[11px] text-slate-500">Generated from the extracted invoice</p>
                    </div>

                    {selectedDoc.proposal && (
                      <span className="px-2.5 py-1 text-xs font-bold rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 flex items-center space-x-1.5">
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-700" />
                        <span>Debits == Credits</span>
                      </span>
                    )}
                  </div>

                  {selectedDoc.proposal ? (
                    <div className="p-5 space-y-5 flex-1 flex flex-col justify-between">
                      <div className="space-y-4">
                        {/* Transaction Type & Narration */}
                        <div className="text-xs space-y-2">
                          <div className="flex items-center space-x-2">
                            <span className="text-slate-500 font-medium">Classification:</span>
                            <span className="font-mono text-[11px] font-bold text-blue-700 bg-blue-50 px-2 py-0.5 rounded border border-blue-200">
                              {selectedDoc.proposal.transaction_type}
                            </span>
                          </div>
                          <div>
                            <span className="text-slate-500 font-medium">Narration:</span>
                            <p className="text-slate-800 italic mt-0.5 leading-relaxed">{selectedDoc.proposal.narration}</p>
                          </div>
                        </div>

                        {/* Double-Entry Table */}
                        <div className="border-y border-slate-200">
                          <table className="w-full text-left text-xs">
                            <thead className="bg-slate-50 text-slate-700 font-semibold border-b border-slate-200 text-[11px]">
                              <tr>
                                <th className="py-2.5 px-3.5">Account Name</th>
                                <th className="py-2.5 px-2">Code</th>
                                <th className="py-2.5 px-3 text-right">Debit (Dr)</th>
                                <th className="py-2.5 px-3.5 text-right">Credit (Cr)</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100">
                              {selectedDoc.proposal.lines.map((line, idx) => (
                                <tr key={idx} className="hover:bg-slate-50">
                                  <td className="py-2.5 px-3.5 font-semibold text-slate-800">
                                    <div className="flex items-center space-x-2">
                                      <span className={`w-2 h-2 rounded-full shrink-0 ${line.entry_type === 'DEBIT' ? 'bg-blue-400' : 'bg-emerald-400'}`}></span>
                                      <span>{line.account_name}</span>
                                    </div>
                                  </td>
                                  <td className="py-2.5 px-2 text-slate-500 font-mono text-[11px] font-bold">{line.account_code}</td>
                                  <td className="py-2.5 px-3 text-right font-mono font-bold text-blue-700">
                                    {line.entry_type === 'DEBIT' ? `₹${line.amount.toFixed(2)}` : '—'}
                                  </td>
                                  <td className="py-2.5 px-3.5 text-right font-mono font-bold text-emerald-700">
                                    {line.entry_type === 'CREDIT' ? `₹${line.amount.toFixed(2)}` : '—'}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                            <tfoot className="bg-[#F5F6F8] font-bold border-t-2 border-slate-200 text-xs">
                              <tr>
                                <td colSpan="2" className="py-3 px-3.5 text-slate-500">Exact Balance Equality</td>
                                <td className="py-3 px-3 text-right font-mono text-blue-700 font-semibold">₹{selectedDoc.proposal.total_debits.toFixed(2)}</td>
                                <td className="py-3 px-3.5 text-right font-mono text-emerald-700 font-semibold">₹{selectedDoc.proposal.total_credits.toFixed(2)}</td>
                              </tr>
                            </tfoot>
                          </table>
                        </div>

                        {/* Applied Policies & Reasoning */}
                        <div className="text-xs border-t border-slate-200 pt-4 space-y-1.5">
                          <span className="font-semibold text-slate-900 block text-xs">Rules applied</span>
                          <ul className="list-disc list-inside space-y-1 text-[11px] text-slate-500">
                            {selectedDoc.proposal.applied_rules?.map((rule, idx) => (
                              <li key={idx} className="leading-relaxed">{rule}</li>
                            ))}
                          </ul>
                        </div>

                      </div>

                      {/* Approval Action */}
                      <div className="pt-4 border-t border-slate-200">
                        {editMode ? (
                          <div className="p-3.5 bg-blue-50 border border-blue-200 rounded-xl text-blue-700 text-xs font-bold flex items-center justify-center space-x-2">
                            <Pencil className="w-4 h-4 shrink-0" />
                            <span>Save or cancel your corrections before posting to the ledger.</span>
                          </div>
                        ) : selectedDoc.status === 'POSTED' ? (
                          <div className="p-3.5 bg-emerald-50 border border-emerald-200 rounded-xl text-emerald-700 text-xs font-bold flex items-center justify-center space-x-2">
                            <CheckCircle2 className="w-4 h-4 text-emerald-700 shrink-0" />
                            <span>This entry has been approved and permanently posted to the General Ledger.</span>
                          </div>
                        ) : selectedDoc.validation_report?.has_blocking_failures ? (
                          <div className="p-3.5 bg-rose-50 border border-rose-200 rounded-xl text-rose-700 text-xs font-bold flex items-center justify-center space-x-2">
                            <XCircle className="w-4 h-4 text-rose-700 shrink-0" />
                            <span>Posting Gate Blocked: Invariant violations must be resolved prior to posting.</span>
                          </div>
                        ) : selectedDoc.proposal?.requires_human_review ? (
                          <button
                            onClick={() => handlePostEntry(false)}
                            disabled={loading}
                            className="w-full py-3.5 bg-amber-600 hover:bg-amber-500 text-slate-950 font-semibold text-xs uppercase tracking-wider rounded-xl transition-all flex items-center justify-center space-x-2 cursor-pointer active:scale-[0.99]"
                          >
                            <AlertTriangle className="w-4 h-4 text-slate-950" />
                            <span>{loading ? 'Posting...' : 'Review & Approve (Override Verification Gate)'}</span>
                          </button>
                        ) : (
                          <button
                            onClick={() => handlePostEntry(true)}
                            disabled={loading}
                            className="w-full py-3.5 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs uppercase tracking-wider rounded-xl transition-all flex items-center justify-center space-x-2 cursor-pointer active:scale-[0.99]"
                          >
                            <CheckCircle2 className="w-4 h-4 text-slate-900" />
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
          <div className="bg-[#FFFFFF] rounded-xl border border-slate-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-200 flex justify-between items-center bg-[#FAFBFC]">
              <p className="text-xs text-slate-500">Immutable, audited records with document provenance.</p>
              <div className="flex items-center space-x-2">
                <ExportButtons report="ledger" />
                <button
                  onClick={() => window.open('/api/reports/export/tally', '_blank')}
                  className="px-2.5 py-1 text-[11px] font-bold rounded-lg bg-slate-100 hover:bg-slate-200 text-blue-700 border border-slate-200 flex items-center space-x-1 cursor-pointer transition-colors"
                  title="Download Tally Prime import XML"
                >
                  <Download className="w-3 h-3" />
                  <span>Tally XML</span>
                </button>
                <button onClick={fetchReports} className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-semibold rounded-lg flex items-center space-x-1.5 border border-slate-200 cursor-pointer">
                  <RefreshCw className="w-3.5 h-3.5 text-slate-500" />
                  <span>Refresh</span>
                </button>
              </div>
            </div>

            {ledgerEntries.length === 0 ? (
              <div className="p-16 text-center text-slate-500 text-sm">
                No posted journal entries yet. Process and approve invoices from Tab 1 to post to the ledger.
              </div>
            ) : (
              <div className="divide-y divide-slate-100">
                {ledgerEntries.map((entry) => (
                  <div key={entry.id} className="p-6 hover:bg-slate-50 transition-colors">
                    <div className="flex justify-between items-start mb-2.5">
                      <div>
                        <span className="font-mono text-xs font-bold text-blue-700 bg-blue-50 border border-blue-200 px-2.5 py-1 rounded-md">
                          Invoice #{entry.invoice_number}
                        </span>
                        <span className="ml-3 text-xs text-slate-500 font-mono">Date: {entry.entry_date}</span>
                      </div>
                      <span className="text-[11px] font-mono text-slate-500 bg-slate-100 px-2.5 py-1 rounded border border-slate-200 font-semibold">
                        {entry.transaction_type}
                      </span>
                    </div>
                    <p className="text-xs text-slate-700 italic mb-3.5 leading-relaxed">{entry.narration}</p>

                    <div className="border border-slate-200 overflow-hidden">
                      <table className="w-full text-left text-xs">
                        <thead className="bg-slate-50 text-slate-700 font-semibold border-b border-slate-200 text-[11px]">
                          <tr>
                            <th className="py-2.5 px-3.5">Account</th>
                            <th className="py-2.5 px-2">Code</th>
                            <th className="py-2.5 px-3 text-right">Debit (₹)</th>
                            <th className="py-2.5 px-3.5 text-right">Credit (₹)</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100 font-mono">
                          {entry.lines.map((l, idx) => (
                            <tr key={idx} className="hover:bg-slate-100/20">
                              <td className="py-2.5 px-3.5 text-slate-800 font-sans font-semibold">{l.account_name}</td>
                              <td className="py-2.5 px-2 text-slate-500 font-bold">{l.account_code}</td>
                              <td className="py-2.5 px-3 text-right font-bold text-blue-700">
                                {l.entry_type === 'DEBIT' ? l.amount.toFixed(2) : '—'}
                              </td>
                              <td className="py-2.5 px-3.5 text-right font-bold text-emerald-700">
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
          <div className="bg-[#FFFFFF] rounded-xl border border-slate-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-200 flex justify-between items-center bg-[#FAFBFC]">
              <p className="text-xs text-slate-500">
                Derived from posted journal lines as of {trialBalance?.as_of_date || 'today'}.
              </p>

              <div className="flex items-center space-x-2">
                <ExportButtons report="trial-balance" />
                {trialBalance?.is_balanced ? (
                  <span className="px-3 py-1 rounded-full text-xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-200 flex items-center space-x-1.5">
                    <CheckCircle2 className="w-4 h-4 text-emerald-700" />
                    <span>Trial Balance Balanced</span>
                  </span>
                ) : (
                  <span className="px-3 py-1 rounded-full text-xs font-bold bg-rose-50 text-rose-700 border border-rose-200 flex items-center space-x-1.5">
                    <AlertTriangle className="w-4 h-4 text-rose-700" />
                    <span>Imbalance Detected</span>
                  </span>
                )}
              </div>
            </div>

            {!trialBalance || trialBalance.rows.length === 0 ? (
              <div className="p-16 text-center text-slate-500 text-sm">
                No active ledger balances. Post an invoice to see the trial balance generate.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-[#F7F8FA] text-slate-700 font-semibold border-b border-slate-200 uppercase tracking-wider text-[11px]">
                    <tr>
                      <th className="py-3 px-5">Account Code</th>
                      <th className="py-3 px-5">Account Name</th>
                      <th className="py-3 px-4">Category</th>
                      <th className="py-3 px-4 text-right">Debit Balance (₹)</th>
                      <th className="py-3 px-5 text-right">Credit Balance (₹)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 font-mono">
                    {trialBalance.rows.map((row) => (
                      <tr key={row.account_code} className="hover:bg-slate-50">
                        <td className="py-2.5 px-5 text-slate-500 font-bold">{row.account_code}</td>
                        <td className="py-2.5 px-5 font-sans font-semibold text-slate-800">{row.account_name}</td>
                        <td className="py-2.5 px-4 font-sans text-slate-500 font-medium">{row.category}</td>
                        <td className="py-2.5 px-4 text-right font-bold text-blue-700">
                          {row.balance_type === 'DEBIT' ? row.closing_balance.toFixed(2) : '—'}
                        </td>
                        <td className="py-2.5 px-5 text-right font-bold text-emerald-700">
                          {row.balance_type === 'CREDIT' ? row.closing_balance.toFixed(2) : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot className="bg-[#F5F6F8] font-bold border-t-2 border-slate-200 font-mono text-xs sm:text-sm">
                    <tr>
                      <td colSpan="3" className="py-3 px-5 font-sans text-slate-900 font-semibold">Total Balance Equality</td>
                      <td className="py-3 px-4 text-right text-blue-700 font-semibold">₹{trialBalance.total_debit_balance.toFixed(2)}</td>
                      <td className="py-3 px-5 text-right text-emerald-700 font-semibold">₹{trialBalance.total_credit_balance.toFixed(2)}</td>
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
            <div className="bg-[#FFFFFF] rounded-xl border border-slate-200 flex flex-col overflow-hidden">
              <div className="p-4 border-b border-slate-200 bg-[#FAFBFC] flex justify-between items-center">
                <h3 className="font-semibold text-sm text-slate-900">Statement of Profit & Loss</h3>
                <div className="flex items-center space-x-3">
                  <span className="text-xs text-slate-500 font-mono">Period ending {profitAndLoss?.as_of_date || 'Current'}</span>
                  <ExportButtons report="profit-and-loss" />
                </div>
              </div>

              {profitAndLoss ? (
                <div className="p-5 space-y-5 text-xs flex-1 flex flex-col justify-between">
                  <div className="space-y-4">
                    <div>
                      <h4 className="font-bold text-slate-500 mb-2 uppercase text-[11px] tracking-wider">Operating Revenue</h4>
                      {profitAndLoss.revenues.length === 0 ? (
                        <p className="text-slate-500 italic text-[11px]">No revenue transactions recorded this period.</p>
                      ) : (
                        profitAndLoss.revenues.map((r, i) => (
                          <div key={i} className="flex justify-between py-1.5 border-b border-slate-200 font-mono">
                            <span className="font-sans text-slate-700 font-semibold">{r.name}</span>
                            <span className="text-slate-800">₹{r.amount.toFixed(2)}</span>
                          </div>
                        ))
                      )}
                      <div className="flex justify-between pt-2.5 font-bold font-mono text-slate-900 text-xs">
                        <span>Total Revenue (A):</span>
                        <span className="text-emerald-700 font-semibold">₹{profitAndLoss.total_revenue.toFixed(2)}</span>
                      </div>
                    </div>

                    <div className="pt-2">
                      <h4 className="font-bold text-slate-500 mb-2 uppercase text-[11px] tracking-wider">Operating Expenses</h4>
                      {profitAndLoss.expenses.length === 0 ? (
                        <p className="text-slate-500 italic text-[11px]">No expense transactions recorded this period.</p>
                      ) : (
                        profitAndLoss.expenses.map((e, i) => (
                          <div key={i} className="flex justify-between py-1.5 border-b border-slate-200 font-mono">
                            <span className="font-sans text-slate-700 font-semibold">{e.name}</span>
                            <span className="text-slate-800">₹{e.amount.toFixed(2)}</span>
                          </div>
                        ))
                      )}
                      <div className="flex justify-between pt-2.5 font-bold font-mono text-slate-900 text-xs">
                        <span>Total Expenses (B):</span>
                        <span className="text-rose-700 font-semibold">₹{profitAndLoss.total_expenses.toFixed(2)}</span>
                      </div>
                    </div>
                  </div>

                  <div className="p-3.5 bg-[#F7F8FA] border border-slate-200 rounded-xl flex justify-between items-center font-bold text-sm">
                    <span className="text-slate-900">Net Operating Profit / (Loss):</span>
                    <span className={profitAndLoss.net_profit >= 0 ? 'text-emerald-700 font-mono font-semibold' : 'text-rose-700 font-mono font-semibold'}>
                      ₹{profitAndLoss.net_profit.toFixed(2)}
                    </span>
                  </div>
                </div>
              ) : (
                <div className="p-12 text-center text-slate-500 text-xs">No P&L data available.</div>
              )}
            </div>

            {/* Balance Sheet */}
            <div className="bg-[#FFFFFF] rounded-xl border border-slate-200 flex flex-col overflow-hidden">
              <div className="p-4 border-b border-slate-200 bg-[#FAFBFC] flex justify-between items-center">
                <h3 className="font-semibold text-sm text-slate-900">Balance Sheet</h3>
                <div className="flex items-center space-x-3">
                  <span className="text-xs text-slate-500 font-mono">As of {balanceSheet?.as_of_date || 'Current'}</span>
                  <ExportButtons report="balance-sheet" />
                </div>
              </div>

              {balanceSheet ? (
                <div className="p-5 space-y-5 text-xs flex-1 flex flex-col justify-between">
                  <div className="space-y-4">
                    <div>
                      <h4 className="font-bold text-slate-500 mb-2 uppercase text-[11px] tracking-wider">Assets</h4>
                      {balanceSheet.assets.map((a, i) => (
                        <div key={i} className="flex justify-between py-1.5 border-b border-slate-200 font-mono">
                          <span className="font-sans text-slate-700 font-semibold">{a.name}</span>
                          <span className="text-slate-800">₹{a.amount.toFixed(2)}</span>
                        </div>
                      ))}
                      <div className="flex justify-between pt-2.5 font-bold font-mono text-blue-700 text-xs">
                        <span>Total Assets:</span>
                        <span className="font-semibold">₹{balanceSheet.total_assets.toFixed(2)}</span>
                      </div>
                    </div>

                    <div className="pt-2">
                      <h4 className="font-bold text-slate-500 mb-2 uppercase text-[11px] tracking-wider">Liabilities & Equity</h4>
                      {balanceSheet.liabilities.map((l, i) => (
                        <div key={i} className="flex justify-between py-1.5 border-b border-slate-200 font-mono">
                          <span className="font-sans text-slate-700 font-semibold">{l.name}</span>
                          <span className="text-slate-800">₹{l.amount.toFixed(2)}</span>
                        </div>
                      ))}
                      <div className="flex justify-between py-1.5 border-b border-slate-200 font-mono text-slate-500">
                        <span className="font-sans">Retained Earnings (from P&L)</span>
                        <span>₹{balanceSheet.retained_earnings.toFixed(2)}</span>
                      </div>
                      <div className="flex justify-between pt-2.5 font-bold font-mono text-emerald-700 text-xs">
                        <span>Total Liabilities & Equity:</span>
                        <span className="font-semibold">₹{balanceSheet.total_liabilities_and_equity.toFixed(2)}</span>
                      </div>
                    </div>
                  </div>

                  <div className={`p-3.5 rounded-xl flex justify-between items-center font-bold text-xs sm:text-sm border ${
                    balanceSheet.is_balanced 
                      ? 'bg-emerald-50 text-emerald-700 border-emerald-200' 
                      : 'bg-rose-50 text-rose-700 border-rose-200'
                  }`}>
                    <span>Balance Sheet Equation:</span>
                    <span className="flex items-center space-x-1.5 font-mono">
                      <CheckCircle2 className="w-4 h-4 text-emerald-700" />
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
          <div className="bg-[#FFFFFF] rounded-xl border border-slate-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-200 bg-[#FAFBFC]">
              <p className="text-xs text-slate-500">Uploads, corrections, postings, and sign-ins, with provenance.</p>
            </div>

            {auditLogs.length === 0 ? (
              <div className="p-16 text-center text-slate-500 text-sm">
                No audit events recorded yet.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-[#F7F8FA] text-slate-700 font-semibold border-b border-slate-200 uppercase tracking-wider text-[11px]">
                    <tr>
                      <th className="py-3 px-5">Timestamp (UTC)</th>
                      <th className="py-3 px-4">Action</th>
                      <th className="py-3 px-4">Entity</th>
                      <th className="py-3 px-4">Performed By</th>
                      <th className="py-3 px-5">Audit Details</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 font-mono">
                    {auditLogs.map((log) => (
                      <tr key={log.id} className="hover:bg-slate-50">
                        <td className="py-2.5 px-5 text-slate-500 text-[11px]">{log.timestamp}</td>
                        <td className="py-2.5 px-4 font-bold text-blue-700">{log.action}</td>
                        <td className="py-2.5 px-4 text-slate-700 font-sans font-semibold">{log.entity_name}</td>
                        <td className="py-2.5 px-4 font-sans text-slate-500">{log.performed_by}</td>
                        <td className="py-2.5 px-5 font-sans text-slate-800">{log.details}</td>
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
      </div>
    </div>
  );
}
