import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { navigateAgentAppRoute } from '../lib/appNavigation'
import { useAuth } from '../hooks/useAuth'
import {
  ReviewRecord,
  ReviewRecordSummary,
  ReviewRecordState
} from '../types'
import { Button } from '../components/ui/Button'
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  ChevronLeft,
  Clock,
  Database,
  FileText,
  Loader2,
  LogOut,
  Search,
  XCircle
} from 'lucide-react'
import { cn } from '@/lib/utils'

export default function ReviewQueue() {
  const { signOut } = useAuth()
  const [summaries, setSummaries] = useState<ReviewRecordSummary[]>([])
  const [selectedRecord, setSelectedRecord] = useState<ReviewRecord | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionLoading, setActionLoading] = useState<string | null>(null)

  useEffect(() => {
    loadSummaries()
  }, [])

  const loadSummaries = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await api.getReviewRecords()
      setSummaries(data)
    } catch (err: any) {
      setError(err.message || 'Failed to load review records')
    } finally {
      setLoading(false)
    }
  }

  const loadRecord = async (recordId: string) => {
    setLoading(true)
    setError(null)
    try {
      const data = await api.getReviewRecord(recordId)
      setSelectedRecord(data)
    } catch (err: any) {
      setError(err.message || 'Failed to load review record details')
    } finally {
      setLoading(false)
    }
  }

  const handleApprove = async (recordId: string, promote = false) => {
    setActionLoading('approve')
    setError(null)
    try {
      const updated = await api.approveReviewRecord(recordId, {
        promote_to_local_corpus: promote,
        review_notes: 'Approved via operator UI'
      })
      setSelectedRecord(updated)
      await loadSummaries()
    } catch (err: any) {
      setError(err.message || 'Failed to approve record')
    } finally {
      setActionLoading(null)
    }
  }

  const handleReject = async (recordId: string) => {
    setActionLoading('reject')
    setError(null)
    try {
      const updated = await api.rejectReviewRecord(recordId, {
        review_notes: 'Rejected via operator UI'
      })
      setSelectedRecord(updated)
      await loadSummaries()
    } catch (err: any) {
      setError(err.message || 'Failed to reject record')
    } finally {
      setActionLoading(null)
    }
  }

  const handlePromote = async (recordId: string) => {
    setActionLoading('promote')
    setError(null)
    try {
      const updated = await api.promoteReviewRecord(recordId)
      setSelectedRecord(updated)
      await loadSummaries()
    } catch (err: any) {
      setError(err.message || 'Failed to promote record')
    } finally {
      setActionLoading(null)
    }
  }

  const handleDemote = async (recordId: string) => {
    setActionLoading('demote')
    setError(null)
    try {
      const updated = await api.demoteReviewRecord(recordId)
      setSelectedRecord(updated)
      await loadSummaries()
    } catch (err: any) {
      setError(err.message || 'Failed to demote record')
    } finally {
      setActionLoading(null)
    }
  }

  const getStatusBadge = (status: ReviewRecordState) => {
    switch (status) {
      case 'approved':
        return <Badge className="bg-green-100 text-green-800 border-green-200">Approved</Badge>
      case 'rejected':
        return <Badge className="bg-red-100 text-red-800 border-red-200">Rejected</Badge>
      case 'draft':
        return <Badge className="bg-blue-100 text-blue-800 border-blue-200">Draft</Badge>
      default:
        return <Badge className="bg-gray-100 text-gray-800 border-gray-200">{status}</Badge>
    }
  }

  if (loading && !summaries.length && !selectedRecord) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] space-y-4">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
        <p className="text-sm font-medium text-slate-500 font-serif italic">Loading review queue...</p>
      </div>
    )
  }

  return (
    <div className="max-w-6xl mx-auto px-6 py-12 space-y-8 animate-in fade-in duration-500">
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <h1 className="text-4xl font-serif text-slate-900 italic">Review Queue</h1>
          <p className="text-slate-500 font-medium font-serif italic">Curate and promote extracted methods to the local corpus.</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={() => navigateAgentAppRoute('/')} className="flex items-center gap-2">
            <ArrowRight className="h-4 w-4 rotate-180" />
            Back to Agent
          </Button>
          {selectedRecord ? (
            <Button variant="ghost" onClick={() => setSelectedRecord(null)} className="flex items-center gap-2">
              <ChevronLeft className="w-4 h-4" />
              Back to Queue
            </Button>
          ) : null}
          <Button variant="ghost" onClick={signOut} className="flex items-center gap-2">
            <LogOut className="h-4 w-4" />
            Sign out
          </Button>
        </div>
      </div>

      {error && (
        <Card className="border-red-200 bg-red-50 rounded-2xl">
          <CardContent className="pt-6 flex items-start gap-4 text-red-800">
            <AlertTriangle className="w-5 h-5 flex-shrink-0 mt-0.5" />
            <div className="space-y-1">
              <p className="font-semibold text-sm">Action Failed</p>
              <p className="text-sm leading-relaxed">{error}</p>
            </div>
          </CardContent>
        </Card>
      )}

      {selectedRecord ? (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="lg:col-span-2 space-y-8">
            <Card className="shadow-none border-slate-200 rounded-[24px]">
              <CardHeader className="pb-4 border-b border-slate-100">
                <div className="flex items-start justify-between">
                  <div className="space-y-2">
                    <div className="flex items-center gap-3">
                      <FileText className="w-5 h-5 text-blue-600" />
                      <CardTitle className="text-2xl font-serif">{selectedRecord.extraction_snapshot.source_document.title || 'Untitled Document'}</CardTitle>
                    </div>
                    <p className="text-sm text-slate-500 line-clamp-2">
                      {selectedRecord.extraction_snapshot.source_document.file_name || selectedRecord.source_document_id}
                    </p>
                  </div>
                  <div className="flex flex-col items-end gap-2">
                    {getStatusBadge(selectedRecord.status)}
                    {selectedRecord.promote_to_local_corpus && (
                      <Badge className="bg-amber-100 text-amber-800 border-amber-200 flex items-center gap-1">
                        <Database className="w-3 h-3" />
                        In Corpus
                      </Badge>
                    )}
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-8 pt-6">
                <div className="grid grid-cols-2 gap-6 bg-slate-50 p-8 rounded-3xl border border-slate-100">
                  <div className="space-y-1">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Mobile Phase A</p>
                    <p className="font-medium text-slate-900">{selectedRecord.extraction_snapshot.method_parameters?.mobile_phase_a.solvent || 'Unknown'}</p>
                  </div>
                  <div className="space-y-1">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Mobile Phase B</p>
                    <p className="font-medium text-slate-900">{selectedRecord.extraction_snapshot.method_parameters?.mobile_phase_b?.solvent || 'n/a'}</p>
                  </div>
                  <div className="space-y-1">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Flow Rate</p>
                    <p className="font-medium text-slate-900">{selectedRecord.extraction_snapshot.method_parameters?.flow_rate_ml_min || 'n/a'} mL/min</p>
                  </div>
                  <div className="space-y-1">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Temperature</p>
                    <p className="font-medium text-slate-900">{selectedRecord.extraction_snapshot.method_parameters?.column_temperature_c || 'n/a'} °C</p>
                  </div>
                </div>

                {selectedRecord.extraction_snapshot.warnings.length > 0 && (
                  <div className="space-y-4">
                    <p className="text-sm font-bold text-slate-900 uppercase tracking-tight">Extraction Warnings</p>
                    <ul className="space-y-2">
                      {selectedRecord.extraction_snapshot.warnings.map((warning, i) => (
                        <li key={i} className="text-sm text-amber-800 bg-amber-50 px-4 py-3 rounded-xl flex items-center gap-3 border border-amber-100/50">
                          <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                          {warning}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          <div className="space-y-6">
            <Card className="shadow-none border-slate-200 rounded-[24px]">
              <CardHeader>
                <CardTitle className="text-lg font-serif">Operator Actions</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 pb-8">
                {selectedRecord.status !== 'approved' && (
                  <Button 
                    className="w-full justify-start gap-3 h-12 bg-blue-600 hover:bg-blue-700"
                    disabled={!!actionLoading}
                    onClick={() => handleApprove(selectedRecord.review_record_id, true)}
                  >
                    {actionLoading === 'approve' ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
                    Approve & Promote
                  </Button>
                )}
                
                {selectedRecord.status === 'approved' && !selectedRecord.promote_to_local_corpus && (
                  <Button 
                    variant="outline"
                    className="w-full justify-start gap-3 h-12 border-slate-200"
                    disabled={!!actionLoading}
                    onClick={() => handlePromote(selectedRecord.review_record_id)}
                  >
                    {actionLoading === 'promote' ? <Loader2 className="w-4 h-4 animate-spin" /> : <Database className="w-4 h-4 text-amber-600" />}
                    Promote to Corpus
                  </Button>
                )}

                {selectedRecord.promote_to_local_corpus && (
                  <Button 
                    variant="outline"
                    className="w-full justify-start gap-3 h-12 border-amber-200 bg-amber-50 text-amber-900 hover:bg-amber-100"
                    disabled={!!actionLoading}
                    onClick={() => handleDemote(selectedRecord.review_record_id)}
                  >
                    {actionLoading === 'demote' ? <Loader2 className="w-4 h-4 animate-spin" /> : <XCircle className="w-4 h-4 text-amber-600" />}
                    Remove from Corpus
                  </Button>
                )}

                {selectedRecord.status !== 'rejected' && (
                  <Button 
                    variant="ghost"
                    className="w-full justify-start gap-3 h-12 text-slate-500 hover:text-red-600 hover:bg-red-50"
                    disabled={!!actionLoading}
                    onClick={() => handleReject(selectedRecord.review_record_id)}
                  >
                    {actionLoading === 'reject' ? <Loader2 className="w-4 h-4 animate-spin" /> : <XCircle className="w-4 h-4" />}
                    Reject Record
                  </Button>
                )}
              </CardContent>
            </Card>

            <Card className="shadow-none border-slate-200 rounded-[24px] bg-slate-50/50">
              <CardContent className="pt-6 space-y-4">
                <div className="flex items-center gap-2 text-slate-400">
                  <Clock className="w-4 h-4" />
                  <p className="text-[10px] font-mono tracking-tight">RECORD_ID: {selectedRecord.review_record_id}</p>
                </div>
                <div className="space-y-1">
                  <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Last Synced</p>
                  <p className="text-sm font-medium text-slate-600">{new Date(selectedRecord.updated_at).toLocaleString()}</p>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      ) : (
        <div className="space-y-6">
          {!summaries.length && !loading ? (
            <Card className="shadow-none border-dashed border-slate-300 py-32 rounded-[32px] bg-slate-50/30">
              <CardContent className="flex flex-col items-center justify-center space-y-6">
                <div className="w-20 h-20 rounded-full bg-white shadow-sm flex items-center justify-center border border-slate-100">
                  <Search className="w-10 h-10 text-slate-200" />
                </div>
                <div className="text-center space-y-2">
                  <p className="font-serif text-2xl text-slate-900">Queue is empty</p>
                  <p className="text-slate-500 font-medium font-serif italic max-w-sm">No records are currently pending curation. Extracted results will appear here for audit.</p>
                </div>
                <Button variant="outline" onClick={loadSummaries} className="mt-4 rounded-full px-8">
                  Refresh Queue
                </Button>
              </CardContent>
            </Card>
          ) : (
            <div className="grid grid-cols-1 gap-4">
              {summaries.map((summary) => (
                <Card 
                  key={summary.review_record_id}
                  className="shadow-none border-slate-200 hover:border-blue-300 hover:shadow-xl hover:shadow-blue-900/5 transition-all cursor-pointer rounded-2xl group"
                  onClick={() => loadRecord(summary.review_record_id)}
                >
                  <CardContent className="p-8">
                    <div className="flex items-start justify-between gap-6">
                      <div className="space-y-3 flex-1">
                        <div className="flex items-center gap-3">
                          <CardTitle className="text-xl font-serif group-hover:text-blue-600 transition-colors leading-tight">{summary.title || 'Untitled Extraction'}</CardTitle>
                          <div className="flex items-center gap-2">
                            {getStatusBadge(summary.status)}
                            {summary.promote_to_local_corpus && (
                              <Badge className="bg-amber-100 text-amber-800 border-amber-200 flex items-center gap-1">
                                <Database className="w-3 h-3" />
                                Corpus
                              </Badge>
                            )}
                          </div>
                        </div>
                        <p className="text-sm text-slate-500 font-serif italic">{summary.citation || 'Source citation unavailable'}</p>
                        <div className="flex items-center gap-6 pt-2">
                          <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400 flex items-center gap-2">
                            <Clock className="w-3 h-3" />
                            {new Date(summary.created_at).toLocaleDateString()}
                          </span>
                          <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400 flex items-center gap-2">
                            <FileText className="w-3 h-3" />
                            {summary.source_document_id}
                          </span>
                        </div>
                      </div>
                      <div className="flex-shrink-0 flex items-center self-center h-full">
                        <Button variant="ghost" size="icon" className="rounded-full opacity-0 group-hover:opacity-100 transition-opacity bg-slate-50">
                          <ArrowRight className="w-5 h-5 text-slate-400" />
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
