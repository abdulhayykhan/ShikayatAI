"use client";

import { useState, useEffect } from "react";

// ─────────────────────────────────────────────────────────────────
// Types — aligned with DrafterResult from agents/drafter.py
// ─────────────────────────────────────────────────────────────────
interface ShikayatResult {
  reference_number: string;
  english_letter: string;
  urdu_letter: string;
  submission_method: "online" | "physical" | "both" | "phone";
  submission_url: string | null;
  helpline_to_call: string | null;
  next_steps_english: string[];
  next_steps_urdu: string[];
}

export default function Home() {
  const [complaint, setComplaint] = useState("");
  const [location, setLocation] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<ShikayatResult | null>(null);
  const [error, setError] = useState<{ english: string; urdu: string } | null>(null);
  const [activeTab, setActiveTab] = useState<"urdu" | "english">("urdu");
  
  const [trackingNumber, setTrackingNumber] = useState("");
  const [isTracking, setIsTracking] = useState(false);

  const [userId, setUserId] = useState("");

  // Initialize User ID
  useEffect(() => {
    let storedUserId = localStorage.getItem("shikayat_user_id");
    if (!storedUserId) {
      storedUserId = "user_" + Math.random().toString(36).substring(2, 9);
      localStorage.setItem("shikayat_user_id", storedUserId);
    }
    setUserId(storedUserId);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (complaint.length < 5) return;

    setIsLoading(true);
    setError(null);
    setResult(null);

    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const response = await fetch(`${baseUrl}/api/complaint`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ complaint, location, user_id: userId }),
      });

      let data;
      const responseText = await response.text();
      try {
        data = JSON.parse(responseText);
      } catch (e) {
        throw new Error(`Server returned non-JSON response (${response.status}): ` + responseText.substring(0, 100));
      }

      if (!response.ok) {
        setError({
          english: data.error_english || "An error occurred.",
          urdu: data.error_urdu || "ایک خامی پیش آ گئی ہے۔"
        });
      } else {
        setResult(data as ShikayatResult);
      }
    } catch (err) {
      setError({
        english: err instanceof Error ? err.message : "Failed to connect to the server.",
        urdu: "سرور سے رابطہ کرنے میں ناکامی۔"
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleTrack = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!trackingNumber) return;

    setIsTracking(true);
    setError(null);
    setResult(null);

    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const response = await fetch(`${baseUrl}/api/complaint/${trackingNumber}`);

      let data;
      const responseText = await response.text();
      try {
        data = JSON.parse(responseText);
      } catch (e) {
        throw new Error(`Server returned non-JSON response (${response.status}): ` + responseText.substring(0, 100));
      }

      if (!response.ok) {
        setError({
          english: data.error_english || "Complaint not found.",
          urdu: data.error_urdu || "شکایت نہیں ملی۔"
        });
      } else {
        setResult(data as ShikayatResult);
      }
    } catch (err) {
      setError({
        english: err instanceof Error ? err.message : "Failed to connect to the server.",
        urdu: "سرور سے رابطہ کرنے میں ناکامی۔"
      });
    } finally {
      setIsTracking(false);
    }
  };

  const getMethodBadge = (method: string) => {
    switch (method) {
      case "online": return "bg-blue-100 text-blue-800 border-blue-200";
      case "phone": return "bg-green-100 text-green-800 border-green-200";
      case "physical": return "bg-orange-100 text-orange-800 border-orange-200";
      case "both": return "bg-purple-100 text-purple-800 border-purple-200";
      default: return "bg-slate-100 text-slate-800 border-slate-200";
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col items-center pb-20">

      {/* Hero Section */}
      <header className="w-full bg-[#1B4332] text-white py-12 px-4 shadow-lg mb-8 text-center border-b-4 border-[#F59E0B]">
        <h1 className="text-5xl font-bold font-urdu mb-4 drop-shadow-md">شکایت درج کریں</h1>
        <p className="text-xl opacity-90 max-w-2xl mx-auto font-light">
          Civic Complaint Resolution System for Karachi
        </p>
      </header>

      <main className="w-full max-w-6xl px-4 grid grid-cols-1 lg:grid-cols-3 gap-8">

        {/* Left Column: Form & History */}
        <div className="lg:col-span-1 space-y-8">

          {/* Track Complaint Form */}
          <div className="bg-white rounded-xl shadow-md border border-slate-200 p-6">
            <h2 className="text-xl font-bold text-[#1B4332] mb-4 border-b pb-2">Track Complaint</h2>
            <form onSubmit={handleTrack} className="flex gap-2">
              <input
                type="text"
                className="w-full p-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#1B4332] focus:border-[#1B4332] outline-none transition"
                placeholder="Reference No. (e.g. KF-2026...)"
                value={trackingNumber}
                onChange={(e) => setTrackingNumber(e.target.value.trim())}
                disabled={isTracking || isLoading}
                required
              />
              <button
                type="submit"
                disabled={isTracking || isLoading || !trackingNumber}
                className="bg-[#1B4332] hover:bg-[#123023] text-white font-bold py-3 px-6 rounded-lg transition-colors disabled:opacity-50 whitespace-nowrap flex items-center"
              >
                {isTracking ? "..." : "Track"}
              </button>
            </form>
          </div>

          {/* Complaint Form */}
          <div className="bg-white rounded-xl shadow-md border border-slate-200 p-6">
            <h2 className="text-xl font-bold text-[#1B4332] mb-6 border-b pb-2">Submit Complaint</h2>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Your Issue</label>
                <textarea
                  className="w-full p-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#1B4332] focus:border-[#1B4332] outline-none transition"
                  rows={5}
                  placeholder="e.g. Teen din se pani nahi aa raha... / Water shortage for 3 days..."
                  value={complaint}
                  onChange={(e) => setComplaint(e.target.value)}
                  disabled={isLoading}
                  required
                  minLength={5}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Location (Optional)</label>
                <input
                  type="text"
                  className="w-full p-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#1B4332] focus:border-[#1B4332] outline-none transition"
                  placeholder="e.g. PECHS Block 2"
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                  disabled={isLoading}
                />
              </div>

              <button
                type="submit"
                disabled={isLoading || complaint.length < 5}
                className="w-full bg-[#1B4332] hover:bg-[#123023] text-white font-bold py-3 px-4 rounded-lg transition-colors disabled:opacity-50 flex justify-center items-center"
              >
                {isLoading ? (
                  <span className="flex items-center gap-2">
                    <svg className="animate-spin h-5 w-5 text-white" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    <span className="font-urdu text-lg">تجزیہ ہو رہا ہے...</span> | Analyzing...
                  </span>
                ) : (
                  <span>Submit / جمع کریں</span>
                )}
              </button>
            </form>
          </div>


        </div>

        {/* Right Column: Results */}
        <div className="lg:col-span-2">
          {error && (
            <div className="bg-red-50 border-l-4 border-red-500 p-4 rounded-r-lg mb-6 shadow-sm">
              <p className="text-red-700 font-bold">Error</p>
              <p className="text-red-600 mb-2">{error.english}</p>
              <p className="text-red-600 font-urdu text-lg" dir="rtl">{error.urdu}</p>
            </div>
          )}

          {!result && !error && !isLoading && (
            <div className="h-full flex flex-col items-center justify-center text-slate-400 p-12 border-2 border-dashed border-slate-200 rounded-xl">
              <svg className="w-16 h-16 mb-4 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
              <p className="text-lg">Your generated complaint will appear here.</p>
              <p className="font-urdu text-xl mt-2">آپ کی تیار کردہ شکایت یہاں ظاہر ہوگی۔</p>
            </div>
          )}

          {result && (
            <div className="bg-white rounded-xl shadow-lg border border-slate-200 overflow-hidden animate-in fade-in slide-in-from-bottom-4 duration-500">

              {/* Header Info */}
              <div className="p-6 border-b border-slate-100 bg-slate-50/50">
                <div className="flex flex-wrap justify-between items-start gap-4 mb-4">
                  <div>
                    <h2 className="text-2xl font-bold text-[#1B4332]">Complaint Letter Ready</h2>
                    <p className="text-slate-500 font-mono text-sm">{result.reference_number}</p>
                  </div>
                  <div className={`px-4 py-1.5 rounded-full border font-bold text-sm uppercase tracking-wider ${getMethodBadge(result.submission_method)}`}>
                    Submit: {result.submission_method}
                  </div>
                </div>

                {/* Action Buttons */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
                  {result.helpline_to_call && (
                    <a
                      href={`tel:${result.helpline_to_call}`}
                      className="flex items-center gap-3 p-4 bg-white border border-slate-200 rounded-lg hover:border-[#1B4332] transition-colors group"
                    >
                      <div className="w-10 h-10 rounded-full bg-green-100 flex items-center justify-center text-green-600 group-hover:bg-green-600 group-hover:text-white transition-colors">
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"></path></svg>
                      </div>
                      <div>
                        <p className="text-xs text-slate-500 uppercase tracking-wide">Helpline</p>
                        <p className="font-bold text-[#1B4332] text-lg">{result.helpline_to_call}</p>
                      </div>
                    </a>
                  )}

                  {result.submission_url && (
                    <a
                      href={result.submission_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-3 p-4 bg-white border border-slate-200 rounded-lg hover:border-[#F59E0B] transition-colors group"
                    >
                      <div className="w-10 h-10 rounded-full bg-orange-100 flex items-center justify-center text-orange-600 group-hover:bg-[#F59E0B] group-hover:text-white transition-colors">
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9"></path></svg>
                      </div>
                      <div>
                        <p className="text-xs text-slate-500 uppercase tracking-wide">Official Portal</p>
                        <p className="font-bold text-[#1B4332] text-lg">Visit Website</p>
                      </div>
                    </a>
                  )}
                </div>
              </div>

              {/* Drafts Section */}
              <div className="p-6">
                <div className="flex border-b border-slate-200 mb-6">
                  <button
                    onClick={() => setActiveTab("urdu")}
                    className={`pb-3 px-6 text-lg font-urdu border-b-2 transition-colors ${activeTab === "urdu" ? "border-[#1B4332] text-[#1B4332] font-bold" : "border-transparent text-slate-500 hover:text-slate-700"}`}
                  >
                    اردو ڈرافٹ
                  </button>
                  <button
                    onClick={() => setActiveTab("english")}
                    className={`pb-3 px-6 font-medium border-b-2 transition-colors ${activeTab === "english" ? "border-[#1B4332] text-[#1B4332] font-bold" : "border-transparent text-slate-500 hover:text-slate-700"}`}
                  >
                    English Draft
                  </button>
                </div>

                <div className="bg-slate-50 p-6 rounded-lg border border-slate-200 relative">
                  <button
                    onClick={() => {
                      const text = activeTab === "english" ? result.english_letter : result.urdu_letter;
                      navigator.clipboard.writeText(text || "");
                    }}
                    className="absolute top-4 right-4 p-2 text-slate-400 hover:text-[#1B4332] hover:bg-slate-200 rounded transition-colors"
                    title="Copy to clipboard"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"></path></svg>
                  </button>

                  {activeTab === "english" ? (
                    <div className="whitespace-pre-wrap text-slate-800 font-serif leading-relaxed">
                      {result.english_letter || "Draft not available."}
                    </div>
                  ) : (
                    <div className="whitespace-pre-wrap text-slate-800 font-urdu text-xl leading-loose text-right" dir="rtl">
                      {result.urdu_letter || "ڈرافٹ دستیاب نہیں ہے۔"}
                    </div>
                  )}
                </div>

                {/* Next Steps */}
                {result.next_steps_english?.length > 0 && (
                  <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <h3 className="font-bold text-[#1B4332] mb-2">Next Steps</h3>
                      <ol className="space-y-1">
                        {result.next_steps_english.map((step, i) => (
                          <li key={i} className="text-sm text-slate-600 flex gap-2">
                            <span className="font-bold text-[#1B4332] shrink-0">{i + 1}.</span>
                            <span>{step}</span>
                          </li>
                        ))}
                      </ol>
                    </div>
                    {result.next_steps_urdu?.length > 0 && (
                      <div dir="rtl">
                        <h3 className="font-bold text-[#1B4332] mb-2 font-urdu">اگلے اقدامات</h3>
                        <ol className="space-y-1">
                          {result.next_steps_urdu.map((step, i) => (
                            <li key={i} className="text-sm text-slate-600 flex gap-2 font-urdu">
                              <span className="font-bold text-[#1B4332] shrink-0">{i + 1}.</span>
                              <span>{step}</span>
                            </li>
                          ))}
                        </ol>
                      </div>
                    )}
                  </div>
                )}

                <div className="mt-6 flex justify-end">
                  <button
                    className="bg-[#F59E0B] hover:bg-[#D97706] text-white font-bold py-2 px-6 rounded-lg transition-colors flex items-center gap-2"
                    onClick={() => {
                      const text = activeTab === "english" ? result.english_letter : result.urdu_letter;
                      const blob = new Blob([text || ""], { type: "text/plain;charset=utf-8" });
                      const url = URL.createObjectURL(blob);
                      const a = document.createElement("a");
                      a.href = url;
                      a.download = `Complaint_${result.reference_number}.txt`;
                      a.click();
                      URL.revokeObjectURL(url);
                    }}
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path></svg>
                    Download Letter
                  </button>
                </div>
              </div>

            </div>
          )}
        </div>
      </main>

      {/* Floating Button with Hover Popover */}
      <div className="fixed bottom-6 left-6 z-50 group">
        {/* The Popover Card (hidden by default, shows on hover) */}
        <div className="absolute bottom-full left-0 mb-4 w-[320px] sm:w-[400px] opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-300 transform translate-y-4 group-hover:translate-y-0 pointer-events-none group-hover:pointer-events-auto">
          <div className="bg-white rounded-2xl shadow-2xl p-5 border border-slate-200 text-left cursor-default">
            <h2 className="text-lg font-bold text-[#1B4332] mb-3 border-b pb-2">How it works</h2>
            
            <div className="space-y-3 text-slate-700 text-sm">
              <div className="bg-slate-50 p-3 rounded-xl border border-slate-100">
                <p className="mb-2"><strong>1. Describe your issue</strong><br/>Tell us your civic problem in plain Urdu, Roman Urdu, or English.</p>
                <p className="mb-2"><strong>2. AI Analysis</strong><br/>Our AI identifies the correct government department and finds contact info.</p>
                <p><strong>3. Get your letter</strong><br/>We instantly draft a formal complaint letter in both English and Urdu.</p>
              </div>

              <div className="bg-[#1B4332]/5 p-3 rounded-xl border border-[#1B4332]/10 text-right font-urdu leading-relaxed" dir="rtl">
                <h2 className="text-lg font-bold text-[#1B4332] mb-2">یہ کیسے کام کرتا ہے</h2>
                <p className="mb-2"><strong>1. مسئلہ بتائیں:</strong> شہری مسئلہ سادہ یا رومن اردو میں لکھیں۔</p>
                <p className="mb-2"><strong>2. اے آئی کا تجزیہ:</strong> متعلقہ محکمے اور رابطے کی تفصیلات تلاش کرتا ہے۔</p>
                <p><strong>3. درخواست حاصل کریں:</strong> فوری طور پر انگریزی اور اردو میں مسودہ تیار۔</p>
              </div>
            </div>
          </div>
        </div>

        {/* The Button Itself */}
        <button
          className="bg-[#1B4332] hover:bg-[#123023] text-white p-4 rounded-full shadow-xl transition-transform hover:scale-110 flex items-center justify-center"
          title="How it works / یہ کیسے کام کرتا ہے"
        >
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
        </button>
      </div>
    </div>
  );
}
