import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  FileText, CheckCircle2, AlertTriangle, ArrowRight, ShieldCheck, 
  BookOpen, Scale, PieChart, History, Upload, RefreshCw, Layers, ExternalLink
} from 'lucide-react';

export default function App() {
  const [activeTab, setActiveTab] = useState('invoices');
  const [tenant, setTenant] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [loading, setLoading] = useState(false);
  const [processingDocId, setProcessingDocId] = useState(null);
  
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
      handleSelectDocument(res.data.document_id);
    } catch (err) {
      setActionMessage({ type: 'error', text: 'Upload failed: ' + (err.response?.data?.detail || err.message) });
    } finally {
      setLoading(false);
    }
  };

  const handleProcessDocument = async (docId) => {
    setProcessingDocId(docId);
    try {
      const res = await axios.post(`/api/documents/${docId}/process`);
      setActionMessage({ type: 'success', text: 'Extracted and generated accounting proposal successfully!' });
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
      setActionMessage({ type: 'success', text: `Posted to General Ledger! ID: ${res.data.journal_entry_id}` });
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

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col text-slate-800">
      {/* Top Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-50 shadow-xs">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-lg bg-indigo-600 flex items-center justify-center text-white font-bold shadow-sm">
              <Scale className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-slate-900 leading-tight">
                AI Accounting Automation System
              </h1>
              <p className="text-xs text-slate-500">
                Multimodal Document Intelligence • Verified Double-Entry Ledger
              </p>
            </div>
          </div>

          {tenant && (
            <div className="flex items-center space-x-4">
              <div className="text-right">
                <span className="text-xs font-semibold uppercase tracking-wider text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded">
                  {tenant.name}
                </span>
                <p className="text-xs text-slate-400 mt-0.5">GSTIN: {tenant.gstin} ({tenant.currency})</p>
              </div>
              <div className="h-8 w-px bg-slate-200"></div>
              <span className="flex items-center text-xs font-medium text-emerald-600 bg-emerald-50 px-2 py-1 rounded-full">
                <span className="w-2 h-2 rounded-full bg-emerald-500 mr-1.5 animate-pulse"></span>
                Engine Online
              </span>
            </div>
          )}
        </div>

        {/* Navigation Tabs */}
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex space-x-1 border-t border-slate-100 overflow-x-auto">
          {[
            { id: 'invoices', label: '1. Invoices & Ingestion', icon: FileText },
            { id: 'review', label: '2. Review & Proposal', icon: ShieldCheck },
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
                className={`flex items-center space-x-2 py-3 px-4 border-b-2 font-medium text-sm transition-colors whitespace-nowrap ${
                  isActive
                    ? 'border-indigo-600 text-indigo-600 font-semibold'
                    : 'border-transparent text-slate-600 hover:text-slate-900 hover:border-slate-300'
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? 'text-indigo-600' : 'text-slate-400'}`} />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>
      </header>

      {/* Global Alerts */}
      {actionMessage && (
        <div className={`py-2 px-4 text-sm font-medium text-center ${
          actionMessage.type === 'success' ? 'bg-emerald-100 text-emerald-800' : 'bg-rose-100 text-rose-800'
        }`}>
          {actionMessage.text}
          <button onClick={() => setActionMessage(null)} className="ml-3 font-bold">×</button>
        </div>
      )}

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 lg:p-8">
        {/* TAB 1: INVOICES & INGESTION */}
        {activeTab === 'invoices' && (
          <div className="space-y-6">
            {/* Upload Area */}
            <div className="bg-white p-6 rounded-xl border border-dashed border-indigo-300 hover:border-indigo-500 transition-colors text-center shadow-xs">
              <Upload className="w-10 h-10 text-indigo-500 mx-auto mb-2" />
              <h3 className="text-base font-semibold text-slate-800">Upload PDF Invoice for Autonomous Processing</h3>
              <p className="text-xs text-slate-500 max-w-md mx-auto mt-1 mb-4">
                Accepts multi-item, digital or scanned invoice PDFs. Runs table-layout correction (Yao et al.) and heuristic extraction (Rana et al.).
              </p>
              <label className="inline-flex items-center px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium rounded-lg cursor-pointer shadow-xs transition">
                <span>Select Invoice PDF</span>
                <input type="file" accept=".pdf" onChange={handleFileUpload} className="hidden" />
              </label>
            </div>

            {/* Invoices List */}
            <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-xs">
              <div className="px-6 py-4 border-b border-slate-200 flex justify-between items-center">
                <h2 className="font-bold text-slate-900 text-sm tracking-wide">Uploaded Documents & Extraction Status</h2>
                <button onClick={fetchDocuments} className="text-xs text-slate-500 hover:text-slate-700 flex items-center space-x-1">
                  <RefreshCw className="w-3.5 h-3.5" />
                  <span>Refresh</span>
                </button>
              </div>

              {documents.length === 0 ? (
                <div className="p-8 text-center text-slate-400 text-sm">
                  No invoices uploaded yet. Upload a PDF or seed samples to begin.
                </div>
              ) : (
                <table className="w-full text-left text-sm">
                  <thead className="bg-slate-50 text-slate-600 font-semibold border-b border-slate-200 text-xs uppercase">
                    <tr>
                      <th className="py-3 px-4">Filename</th>
                      <th className="py-3 px-4">Invoice #</th>
                      <th className="py-3 px-4">Vendor</th>
                      <th className="py-3 px-4 text-right">Grand Total</th>
                      <th className="py-3 px-4">Status</th>
                      <th className="py-3 px-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {documents.map((doc) => (
                      <tr key={doc.id} className="hover:bg-slate-50/80 transition-colors">
                        <td className="py-3 px-4 font-medium text-slate-900 flex items-center space-x-2">
                          <FileText className="w-4 h-4 text-slate-400" />
                          <span className="truncate max-w-xs">{doc.filename}</span>
                        </td>
                        <td className="py-3 px-4 text-slate-700 font-mono text-xs">{doc.invoice_number || '—'}</td>
                        <td className="py-3 px-4 text-slate-700">{doc.vendor_name || '—'}</td>
                        <td className="py-3 px-4 text-right font-semibold text-slate-900">
                          {doc.grand_total ? `₹${doc.grand_total.toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : '—'}
                        </td>
                        <td className="py-3 px-4">
                          <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold ${
                            doc.status === 'POSTED' ? 'bg-emerald-100 text-emerald-800' :
                            doc.status === 'PROCESSED' ? 'bg-blue-100 text-blue-800' :
                            doc.status === 'REVIEW_REQUIRED' ? 'bg-amber-100 text-amber-800' :
                            'bg-slate-100 text-slate-700'
                          }`}>
                            {doc.status}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-right space-x-2">
                          {doc.status === 'UPLOADED' && (
                            <button
                              onClick={() => handleProcessDocument(doc.id)}
                              disabled={processingDocId === doc.id}
                              className="px-3 py-1 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded shadow-xs"
                            >
                              {processingDocId === doc.id ? 'Processing...' : 'Run Extraction'}
                            </button>
                          )}
                          <button
                            onClick={() => handleSelectDocument(doc.id)}
                            className="px-3 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded"
                          >
                            Review & Post
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        )}

        {/* TAB 2: REVIEW & PROPOSAL (SIDE-BY-SIDE) */}
        {activeTab === 'review' && (
          <div>
            {!selectedDoc ? (
              <div className="bg-white p-12 text-center rounded-xl border border-slate-200">
                <ShieldCheck className="w-12 h-12 text-slate-300 mx-auto mb-3" />
                <h3 className="text-base font-semibold text-slate-700">No Document Selected</h3>
                <p className="text-xs text-slate-400 mt-1 mb-4">Please select an invoice from Tab 1 to inspect extraction and accounting proposals.</p>
                <button onClick={() => setActiveTab('invoices')} className="px-4 py-2 bg-indigo-600 text-white text-xs font-medium rounded-lg">
                  Back to Invoices
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* LEFT COLUMN: Extracted Document & Line Items */}
                <div className="bg-white rounded-xl border border-slate-200 shadow-xs flex flex-col">
                  <div className="p-4 border-b border-slate-200 bg-slate-50 flex justify-between items-center">
                    <div>
                      <h2 className="text-sm font-bold text-slate-900">Extracted Invoice Metadata & Table</h2>
                      <p className="text-xs text-slate-500 font-mono">{selectedDoc.filename}</p>
                    </div>
                    <span className="px-2 py-0.5 text-xs font-semibold rounded bg-indigo-100 text-indigo-800">
                      Status: {selectedDoc.status}
                    </span>
                  </div>

                  {selectedDoc.invoice ? (
                    <div className="p-5 space-y-5 flex-1">
                      {/* Metadata Grid */}
                      <div className="grid grid-cols-2 gap-3 bg-slate-50 p-3 rounded-lg border border-slate-200 text-xs">
                        <div>
                          <span className="text-slate-400">Invoice Number:</span>
                          <p className="font-bold text-slate-800 font-mono">{selectedDoc.invoice.invoice_number}</p>
                        </div>
                        <div>
                          <span className="text-slate-400">Invoice Date:</span>
                          <p className="font-bold text-slate-800">{selectedDoc.invoice.invoice_date}</p>
                        </div>
                        <div>
                          <span className="text-slate-400">Vendor / Supplier:</span>
                          <p className="font-bold text-slate-800">{selectedDoc.invoice.vendor_name}</p>
                          <p className="text-slate-400 font-mono text-[10px]">GSTIN: {selectedDoc.invoice.vendor_gstin || 'N/A'}</p>
                        </div>
                        <div>
                          <span className="text-slate-400">Buyer / Customer:</span>
                          <p className="font-bold text-slate-800">{selectedDoc.invoice.buyer_name || 'Modern Tech Solutions'}</p>
                          <p className="text-slate-400 font-mono text-[10px]">GSTIN: {selectedDoc.invoice.buyer_gstin || 'N/A'}</p>
                        </div>
                      </div>

                      {/* Reconstructed Line Items Table */}
                      <div>
                        <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
                          Reconstructed Line Items (Table Layout Corrected)
                        </h4>
                        <div className="border border-slate-200 rounded-lg overflow-hidden">
                          <table className="w-full text-left text-xs">
                            <thead className="bg-slate-100 text-slate-600 font-semibold">
                              <tr>
                                <th className="py-2 px-3">Item Description</th>
                                <th className="py-2 px-2">HSN</th>
                                <th className="py-2 px-2 text-right">Qty</th>
                                <th className="py-2 px-2 text-right">Unit Price</th>
                                <th className="py-2 px-2 text-right">Disc</th>
                                <th className="py-2 px-3 text-right">Total</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100">
                              {selectedDoc.invoice.line_items.map((item, idx) => (
                                <tr key={idx} className="hover:bg-slate-50">
                                  <td className="py-2 px-3 font-medium text-slate-900">{item.description}</td>
                                  <td className="py-2 px-2 text-slate-500 font-mono text-[11px]">{item.hsn_sac || '-'}</td>
                                  <td className="py-2 px-2 text-right">{item.quantity}</td>
                                  <td className="py-2 px-2 text-right">₹{item.unit_price.toFixed(2)}</td>
                                  <td className="py-2 px-2 text-right text-slate-500">{item.discount_amount > 0 ? `₹${item.discount_amount.toFixed(2)}` : '—'}</td>
                                  <td className="py-2 px-3 text-right font-semibold text-slate-900">₹{item.total_amount.toFixed(2)}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>

                      {/* Totals Summary */}
                      <div className="bg-slate-50 p-3 rounded-lg border border-slate-200 text-xs space-y-1">
                        <div className="flex justify-between">
                          <span className="text-slate-500">Taxable Subtotal:</span>
                          <span className="font-semibold text-slate-800">₹{selectedDoc.invoice.subtotal.toFixed(2)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-500">Total Tax (GST):</span>
                          <span className="font-semibold text-slate-800">₹{selectedDoc.invoice.total_tax.toFixed(2)}</span>
                        </div>
                        {selectedDoc.invoice.total_discount > 0 && (
                          <div className="flex justify-between text-emerald-600">
                            <span>Discount:</span>
                            <span>-₹{selectedDoc.invoice.total_discount.toFixed(2)}</span>
                          </div>
                        )}
                        <div className="flex justify-between pt-2 border-t border-slate-200 font-bold text-sm text-indigo-900">
                          <span>Grand Total Payable:</span>
                          <span>₹{selectedDoc.invoice.grand_total.toFixed(2)}</span>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="p-8 text-center text-slate-400 text-xs">
                      Document not processed yet.
                    </div>
                  )}
                </div>

                {/* RIGHT COLUMN: AI Accounting Proposal & Invariant Verification */}
                <div className="bg-white rounded-xl border border-slate-200 shadow-xs flex flex-col">
                  <div className="p-4 border-b border-slate-200 bg-indigo-50/50 flex justify-between items-center">
                    <div>
                      <h2 className="text-sm font-bold text-indigo-950 flex items-center space-x-1.5">
                        <Scale className="w-4 h-4 text-indigo-600" />
                        <span>Proposed Double-Entry Journal</span>
                      </h2>
                      <p className="text-xs text-indigo-600/80">Deterministic Invariant Verified</p>
                    </div>

                    {selectedDoc.proposal && (
                      <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-emerald-100 text-emerald-800 flex items-center space-x-1">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        <span>Debits == Credits</span>
                      </span>
                    )}
                  </div>

                  {selectedDoc.proposal ? (
                    <div className="p-5 space-y-5 flex-1 flex flex-col justify-between">
                      <div className="space-y-4">
                        {/* Transaction Type & Narration */}
                        <div className="bg-indigo-50/40 p-3 rounded-lg border border-indigo-100 text-xs space-y-1.5">
                          <div className="flex items-center space-x-2">
                            <span className="font-semibold text-slate-600">Classification:</span>
                            <span className="font-mono text-[11px] font-bold text-indigo-700 bg-white px-2 py-0.5 rounded border border-indigo-200">
                              {selectedDoc.proposal.transaction_type}
                            </span>
                          </div>
                          <div>
                            <span className="font-semibold text-slate-600">Narration:</span>
                            <p className="text-slate-800 italic mt-0.5">{selectedDoc.proposal.narration}</p>
                          </div>
                        </div>

                        {/* Double-Entry Table */}
                        <div className="border border-slate-200 rounded-lg overflow-hidden">
                          <table className="w-full text-left text-xs">
                            <thead className="bg-slate-100 text-slate-700 font-semibold">
                              <tr>
                                <th className="py-2.5 px-3">Account Name</th>
                                <th className="py-2.5 px-2">Code</th>
                                <th className="py-2.5 px-3 text-right">Debit (Dr)</th>
                                <th className="py-2.5 px-3 text-right">Credit (Cr)</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100">
                              {selectedDoc.proposal.lines.map((line, idx) => (
                                <tr key={idx} className="hover:bg-slate-50">
                                  <td className="py-2.5 px-3 font-medium text-slate-900">
                                    <div className="flex items-center space-x-1.5">
                                      <span className={`w-1.5 h-1.5 rounded-full ${line.entry_type === 'DEBIT' ? 'bg-blue-500' : 'bg-emerald-500'}`}></span>
                                      <span>{line.account_name}</span>
                                    </div>
                                  </td>
                                  <td className="py-2.5 px-2 text-slate-400 font-mono">{line.account_code}</td>
                                  <td className="py-2.5 px-3 text-right font-mono font-semibold text-blue-700">
                                    {line.entry_type === 'DEBIT' ? `₹${line.amount.toFixed(2)}` : '—'}
                                  </td>
                                  <td className="py-2.5 px-3 text-right font-mono font-semibold text-emerald-700">
                                    {line.entry_type === 'CREDIT' ? `₹${line.amount.toFixed(2)}` : '—'}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                            <tfoot className="bg-slate-50 font-bold border-t border-slate-200 text-xs">
                              <tr>
                                <td colSpan="2" className="py-2.5 px-3 text-slate-700">Total Verification</td>
                                <td className="py-2.5 px-3 text-right font-mono text-blue-900">₹{selectedDoc.proposal.total_debits.toFixed(2)}</td>
                                <td className="py-2.5 px-3 text-right font-mono text-emerald-900">₹{selectedDoc.proposal.total_credits.toFixed(2)}</td>
                              </tr>
                            </tfoot>
                          </table>
                        </div>

                        {/* Applied Policies & Reasoning */}
                        <div className="text-xs text-slate-500 bg-slate-50 p-3 rounded-lg border border-slate-200 space-y-1">
                          <span className="font-semibold text-slate-700">Applied Accounting Rules:</span>
                          <ul className="list-disc list-inside space-y-0.5 text-[11px] text-slate-600">
                            {selectedDoc.proposal.applied_rules?.map((rule, idx) => (
                              <li key={idx}>{rule}</li>
                            ))}
                          </ul>
                        </div>
                      </div>

                      {/* Approval Action */}
                      <div className="pt-4 border-t border-slate-200">
                        {selectedDoc.status === 'POSTED' ? (
                          <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-emerald-800 text-xs font-semibold flex items-center justify-center space-x-2">
                            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                            <span>This entry has been approved and permanently posted to the General Ledger.</span>
                          </div>
                        ) : (
                          <button
                            onClick={handlePostEntry}
                            disabled={loading}
                            className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-sm rounded-lg shadow-sm transition-colors flex items-center justify-center space-x-2 cursor-pointer"
                          >
                            <CheckCircle2 className="w-4 h-4" />
                            <span>{loading ? 'Posting...' : 'Approve & Post to General Ledger'}</span>
                          </button>
                        )}
                      </div>
                    </div>
                  ) : (
                    <div className="p-8 text-center text-slate-400 text-xs">
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
          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-xs">
            <div className="px-6 py-4 border-b border-slate-200 flex justify-between items-center bg-slate-50">
              <div>
                <h2 className="text-sm font-bold text-slate-900">General Ledger (Posted Double-Entry Journal)</h2>
                <p className="text-xs text-slate-500">Immutable financial records with full document provenance.</p>
              </div>
              <button onClick={fetchReports} className="text-xs text-slate-500 hover:text-slate-700 flex items-center space-x-1">
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Refresh</span>
              </button>
            </div>

            {ledgerEntries.length === 0 ? (
              <div className="p-12 text-center text-slate-400 text-sm">
                No posted journal entries yet. Process and approve invoices to populate the ledger.
              </div>
            ) : (
              <div className="divide-y divide-slate-200">
                {ledgerEntries.map((entry) => (
                  <div key={entry.id} className="p-5 hover:bg-slate-50/50 transition">
                    <div className="flex justify-between items-start mb-2">
                      <div>
                        <span className="font-mono text-xs font-bold text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded border border-indigo-100">
                          Invoice #{entry.invoice_number}
                        </span>
                        <span className="ml-3 text-xs text-slate-500">Date: {entry.entry_date}</span>
                      </div>
                      <span className="text-xs font-mono text-slate-400">{entry.transaction_type}</span>
                    </div>
                    <p className="text-xs text-slate-700 italic mb-3">{entry.narration}</p>

                    <table className="w-full text-left text-xs bg-slate-50 rounded border border-slate-200">
                      <thead className="text-slate-600 font-semibold border-b border-slate-200">
                        <tr>
                          <th className="py-1.5 px-3">Account</th>
                          <th className="py-1.5 px-2">Code</th>
                          <th className="py-1.5 px-3 text-right">Debit (₹)</th>
                          <th className="py-1.5 px-3 text-right">Credit (₹)</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-200/60 font-mono">
                        {entry.lines.map((l, idx) => (
                          <tr key={idx}>
                            <td className="py-1.5 px-3 text-slate-800 font-sans">{l.account_name}</td>
                            <td className="py-1.5 px-2 text-slate-400">{l.account_code}</td>
                            <td className="py-1.5 px-3 text-right font-semibold text-blue-700">
                              {l.entry_type === 'DEBIT' ? l.amount.toFixed(2) : '—'}
                            </td>
                            <td className="py-1.5 px-3 text-right font-semibold text-emerald-700">
                              {l.entry_type === 'CREDIT' ? l.amount.toFixed(2) : '—'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* TAB 4: TRIAL BALANCE */}
        {activeTab === 'trial-balance' && (
          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-xs">
            <div className="px-6 py-4 border-b border-slate-200 flex justify-between items-center bg-slate-50">
              <div>
                <h2 className="text-sm font-bold text-slate-900">Authoritative Trial Balance</h2>
                <p className="text-xs text-slate-500">
                  Dynamically aggregated from posted double-entry journal lines as of {trialBalance?.as_of_date || 'Today'}.
                </p>
              </div>

              {trialBalance?.is_balanced ? (
                <span className="px-3 py-1 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 flex items-center space-x-1.5">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                  <span>Trial Balance In Balance</span>
                </span>
              ) : (
                <span className="px-3 py-1 rounded-full text-xs font-bold bg-rose-100 text-rose-800 flex items-center space-x-1.5">
                  <AlertTriangle className="w-4 h-4 text-rose-600" />
                  <span>Imbalance Detected</span>
                </span>
              )}
            </div>

            {!trialBalance || trialBalance.rows.length === 0 ? (
              <div className="p-12 text-center text-slate-400 text-sm">
                No posted ledger accounts with active balances yet.
              </div>
            ) : (
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-100 text-slate-600 font-semibold border-b border-slate-200">
                  <tr>
                    <th className="py-3 px-4">Account Code</th>
                    <th className="py-3 px-4">Account Name</th>
                    <th className="py-3 px-4">Category</th>
                    <th className="py-3 px-4 text-right">Debit Balance (₹)</th>
                    <th className="py-3 px-4 text-right">Credit Balance (₹)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 font-mono">
                  {trialBalance.rows.map((row) => (
                    <tr key={row.account_code} className="hover:bg-slate-50">
                      <td className="py-2.5 px-4 text-slate-500">{row.account_code}</td>
                      <td className="py-2.5 px-4 font-sans font-medium text-slate-900">{row.account_name}</td>
                      <td className="py-2.5 px-4 font-sans text-slate-500">{row.category}</td>
                      <td className="py-2.5 px-4 text-right font-semibold text-blue-700">
                        {row.balance_type === 'DEBIT' ? row.closing_balance.toFixed(2) : '—'}
                      </td>
                      <td className="py-2.5 px-4 text-right font-semibold text-emerald-700">
                        {row.balance_type === 'CREDIT' ? row.closing_balance.toFixed(2) : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot className="bg-slate-100 font-bold border-t-2 border-slate-300 font-mono text-sm">
                  <tr>
                    <td colSpan="3" className="py-3 px-4 font-sans text-slate-800">Total Balance Equality</td>
                    <td className="py-3 px-4 text-right text-blue-900">₹{trialBalance.total_debit_balance.toFixed(2)}</td>
                    <td className="py-3 px-4 text-right text-emerald-900">₹{trialBalance.total_credit_balance.toFixed(2)}</td>
                  </tr>
                </tfoot>
              </table>
            )}
          </div>
        )}

        {/* TAB 5: FINANCIAL STATEMENTS (P&L AND BALANCE SHEET) */}
        {activeTab === 'statements' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Profit & Loss Statement */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-xs flex flex-col">
              <div className="p-4 border-b border-slate-200 bg-slate-50 flex justify-between items-center">
                <h3 className="font-bold text-sm text-slate-900">Statement of Profit & Loss</h3>
                <span className="text-xs text-slate-500">Period ending {profitAndLoss?.as_of_date || 'Current'}</span>
              </div>

              {profitAndLoss ? (
                <div className="p-5 space-y-4 text-xs flex-1 flex flex-col justify-between">
                  <div className="space-y-3">
                    <div>
                      <h4 className="font-bold text-slate-700 mb-1.5 uppercase text-[11px]">Revenue / Income</h4>
                      {profitAndLoss.revenues.length === 0 ? (
                        <p className="text-slate-400 italic">No revenue posted this period.</p>
                      ) : (
                        profitAndLoss.revenues.map((r, i) => (
                          <div key={i} className="flex justify-between py-1 border-b border-slate-100 font-mono">
                            <span className="font-sans text-slate-800">{r.name}</span>
                            <span>₹{r.amount.toFixed(2)}</span>
                          </div>
                        ))
                      )}
                      <div className="flex justify-between pt-1.5 font-bold font-mono text-slate-900">
                        <span>Total Revenue (A):</span>
                        <span>₹{profitAndLoss.total_revenue.toFixed(2)}</span>
                      </div>
                    </div>

                    <div className="pt-2">
                      <h4 className="font-bold text-slate-700 mb-1.5 uppercase text-[11px]">Operating Expenses</h4>
                      {profitAndLoss.expenses.length === 0 ? (
                        <p className="text-slate-400 italic">No expenses posted this period.</p>
                      ) : (
                        profitAndLoss.expenses.map((e, i) => (
                          <div key={i} className="flex justify-between py-1 border-b border-slate-100 font-mono">
                            <span className="font-sans text-slate-800">{e.name}</span>
                            <span>₹{e.amount.toFixed(2)}</span>
                          </div>
                        ))
                      )}
                      <div className="flex justify-between pt-1.5 font-bold font-mono text-slate-900">
                        <span>Total Expenses (B):</span>
                        <span>₹{profitAndLoss.total_expenses.toFixed(2)}</span>
                      </div>
                    </div>
                  </div>

                  <div className="p-3 bg-slate-100 rounded-lg flex justify-between items-center font-bold text-sm">
                    <span>Net Profit / (Loss):</span>
                    <span className={profitAndLoss.net_profit >= 0 ? 'text-emerald-700 font-mono' : 'text-rose-700 font-mono'}>
                      ₹{profitAndLoss.net_profit.toFixed(2)}
                    </span>
                  </div>
                </div>
              ) : (
                <div className="p-8 text-center text-slate-400 text-xs">No P&L data.</div>
              )}
            </div>

            {/* Balance Sheet */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-xs flex flex-col">
              <div className="p-4 border-b border-slate-200 bg-slate-50 flex justify-between items-center">
                <h3 className="font-bold text-sm text-slate-900">Balance Sheet</h3>
                <span className="text-xs text-slate-500">As of {balanceSheet?.as_of_date || 'Current'}</span>
              </div>

              {balanceSheet ? (
                <div className="p-5 space-y-4 text-xs flex-1 flex flex-col justify-between">
                  <div className="space-y-3">
                    <div>
                      <h4 className="font-bold text-slate-700 mb-1.5 uppercase text-[11px]">Assets</h4>
                      {balanceSheet.assets.map((a, i) => (
                        <div key={i} className="flex justify-between py-1 border-b border-slate-100 font-mono">
                          <span className="font-sans text-slate-800">{a.name}</span>
                          <span>₹{a.amount.toFixed(2)}</span>
                        </div>
                      ))}
                      <div className="flex justify-between pt-1.5 font-bold font-mono text-blue-900">
                        <span>Total Assets:</span>
                        <span>₹{balanceSheet.total_assets.toFixed(2)}</span>
                      </div>
                    </div>

                    <div className="pt-2">
                      <h4 className="font-bold text-slate-700 mb-1.5 uppercase text-[11px]">Liabilities & Equity</h4>
                      {balanceSheet.liabilities.map((l, i) => (
                        <div key={i} className="flex justify-between py-1 border-b border-slate-100 font-mono">
                          <span className="font-sans text-slate-800">{l.name}</span>
                          <span>₹{l.amount.toFixed(2)}</span>
                        </div>
                      ))}
                      <div className="flex justify-between py-1 border-b border-slate-100 font-mono text-slate-600">
                        <span className="font-sans">Retained Earnings (from P&L)</span>
                        <span>₹{balanceSheet.retained_earnings.toFixed(2)}</span>
                      </div>
                      <div className="flex justify-between pt-1.5 font-bold font-mono text-emerald-900">
                        <span>Total Liabilities & Equity:</span>
                        <span>₹{balanceSheet.total_liabilities_and_equity.toFixed(2)}</span>
                      </div>
                    </div>
                  </div>

                  <div className={`p-3 rounded-lg flex justify-between items-center font-bold text-sm ${
                    balanceSheet.is_balanced ? 'bg-emerald-50 text-emerald-900 border border-emerald-200' : 'bg-rose-50 text-rose-900 border border-rose-200'
                  }`}>
                    <span>Balance Sheet Equation:</span>
                    <span>{balanceSheet.is_balanced ? 'Assets == Liab + Equity (Balanced)' : 'Imbalance'}</span>
                  </div>
                </div>
              ) : (
                <div className="p-8 text-center text-slate-400 text-xs">No Balance Sheet data.</div>
              )}
            </div>
          </div>
        )}

        {/* TAB 6: AUDIT TRAIL */}
        {activeTab === 'audit' && (
          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-xs">
            <div className="px-6 py-4 border-b border-slate-200 bg-slate-50">
              <h2 className="text-sm font-bold text-slate-900">Immutable System Audit Trail</h2>
              <p className="text-xs text-slate-500">Every action, invoice ingestion, and posting recorded for compliance.</p>
            </div>

            {auditLogs.length === 0 ? (
              <div className="p-12 text-center text-slate-400 text-sm">
                No audit events recorded yet.
              </div>
            ) : (
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-100 text-slate-600 font-semibold border-b border-slate-200">
                  <tr>
                    <th className="py-2.5 px-4">Timestamp (UTC)</th>
                    <th className="py-2.5 px-4">Action</th>
                    <th className="py-2.5 px-4">Entity</th>
                    <th className="py-2.5 px-4">Performed By</th>
                    <th className="py-2.5 px-4">Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 font-mono">
                  {auditLogs.map((log) => (
                    <tr key={log.id} className="hover:bg-slate-50">
                      <td className="py-2.5 px-4 text-slate-500">{log.timestamp}</td>
                      <td className="py-2.5 px-4 font-bold text-indigo-700">{log.action}</td>
                      <td className="py-2.5 px-4 text-slate-700">{log.entity_name}</td>
                      <td className="py-2.5 px-4 font-sans text-slate-600">{log.performed_by}</td>
                      <td className="py-2.5 px-4 font-sans text-slate-800">{log.details}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
