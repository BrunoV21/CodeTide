import { Card, CardHeader, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ChevronDown, ChevronRight, Brain } from "lucide-react";
import { useState, useEffect } from "react";

export default function ReasoningStepsCard() {
  const [expandedAll, setExpandedAll] = useState(false);
  const [waveOffset, setWaveOffset] = useState(0);
  const [loadingText, setLoadingText] = useState("Analyzing");
  const [thinkingTime, setThinkingTime] = useState(0);

  const loadingStates = ["Analyzing", "Thinking", "Updating", "Processing"];

  useEffect(() => {
    const waveInterval = setInterval(() => {
      setWaveOffset((prev) => (prev + 1) % 360);
    }, 50);

    const textInterval = setInterval(() => {
      setLoadingText((prev) => {
        const idx = loadingStates.indexOf(prev);
        return loadingStates[(idx + 1) % loadingStates.length];
      });
    }, 1000);

    return () => {
      clearInterval(waveInterval);
      clearInterval(textInterval);
    };
  }, []);

  useEffect(() => {
    if (!props.finished) {
      const timer = setInterval(() => {
        setThinkingTime((prev) => prev + 1);
      }, 1000);
      return () => clearInterval(timer);
    }
  }, [props.finished]);

  const toggleAll = () => setExpandedAll(!expandedAll);

  const isLoadingState = !props.finished;

  const getPreviewText = () => {
    if (props.summary) return props.summary.split("\n")[0];
    if (props.reasoning_steps?.length > 0)
      return props.reasoning_steps.at(-1).content.split("\n")[0];
    if (props.finished) return "Finished";
    return `${loadingText}...`;
  };

  const previewText = getPreviewText();

  return (
    <Card className="w-full bg-gradient-to-b from-slate-900 to-slate-950 border-slate-800 transition-all duration-300">
      {/* Header */}
      <CardHeader
        className={`px-6 border-b border-slate-700/50 transition-all duration-300 ${
          expandedAll ? "py-4" : "py-3"
        }`}
      >
        <button
          onClick={toggleAll}
          className="w-full flex items-center justify-between gap-4 hover:opacity-80 transition text-left group"
        >
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-3">
              {isLoadingState && (
                <svg
                  className="w-5 h-5 opacity-60 flex-shrink-0"
                  viewBox="0 0 100 60"
                >
                  <defs>
                    <style>{`
                      @keyframes wave-motion {
                        0%, 100% { d: path('M0,30 Q25,20,50,30 T100,30 L100,60 L0,60'); }
                        50% { d: path('M0,30 Q25,40,50,30 T100,30 L100,60 L0,60'); }
                      }
                      .wave-fill { fill: url(#waveGradient); animation: wave-motion 3s ease-in-out infinite; }
                    `}</style>
                    <linearGradient id="waveGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                      <stop
                        offset="0%"
                        stopColor="rgb(96, 165, 250)"
                        stopOpacity="0.5"
                      />
                      <stop
                        offset="100%"
                        stopColor="rgb(96, 165, 250)"
                        stopOpacity="0.1"
                      />
                    </linearGradient>
                  </defs>
                  <path
                    d="M0,30 Q25,20,50,30 T100,30 L100,60 L0,60"
                    className="wave-fill"
                  />
                </svg>
              )}
              <div
                className={`flex-1 min-w-0 overflow-hidden transition-all duration-300 ${
                  expandedAll ? "space-y-2" : ""
                }`}
              >
                {expandedAll && props.finished && (
                  <p className="text-xs text-slate-500 font-medium">
                    Thought for {thinkingTime}s
                  </p>
                )}
                <p
                  className={`text-slate-200 transition-all duration-300 truncate ${
                    expandedAll
                      ? "text-sm leading-relaxed"
                      : "text-xs opacity-75"
                  }`}
                >
                  {previewText}
                </p>
              </div>
            </div>
          </div>
          <div className="flex-shrink-0 p-1">
            {expandedAll ? (
              <ChevronDown className="h-4 w-4 text-slate-400" />
            ) : (
              <ChevronRight className="h-4 w-4 text-slate-400" />
            )}
          </div>
        </button>
      </CardHeader>

      {/* Expanded Content */}
      {expandedAll && (
        <CardContent className="px-6 py-6 animate-in fade-in slide-in-from-top duration-300">
          {/* Reasoning Steps */}
          {props.reasoning_steps?.map((step, index) => (
            <div key={index}>
              <div className="relative flex gap-4">
                {/* Timeline */}
                <div className="flex flex-col items-center pt-0.5 flex-shrink-0">
                  <div className="w-6 h-6 rounded-full bg-blue-500/20 border border-blue-500/40 flex items-center justify-center">
                    <Brain className="w-3 h-3 text-blue-400" />
                  </div>
                </div>

                {/* Step Content */}
                <div className="flex-1 pt-0.5">
                  <h3 className="text-sm font-semibold text-slate-100 mb-2">
                    {step.header}
                  </h3>
                  <p className="text-xs text-slate-400 leading-relaxed">
                    {step.content}
                  </p>

                  {/* Identifiers — always visible */}
                  {step.candidate_identifiers?.length > 0 && (
                    <div className="mt-4 p-4 bg-slate-800/30 border border-slate-700/50 rounded-lg">
                      <p className="text-xs font-medium text-slate-500 mb-4">
                        Context Identifiers
                      </p>
                      <div className="flex flex-wrap gap-2">
                        {step.candidate_identifiers.map((id, idIndex) => (
                          <Badge
                            key={idIndex}
                            variant="outline"
                            className="text-xs bg-slate-700/50 border-slate-600/50 text-slate-300 hover:bg-slate-700"
                          >
                            {id}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Connector line */}
              {index < props.reasoning_steps.length - 1 && (
                <div className="relative flex gap-4 mt-6">
                  <div className="w-6 flex justify-center flex-shrink-0">
                    <div
                      className="w-px bg-gradient-to-b from-orange-500 to-transparent"
                      style={{ height: "28px" }}
                    ></div>
                  </div>
                </div>
              )}
            </div>
          ))}

          {/* Context + Modify Identifiers — always visible */}
          {(props.context_identifiers?.length > 0 ||
            props.modify_identifiers?.length > 0) && (
            <div className="mt-6 pt-6 border-t border-slate-700/50 space-y-6">
              {props.context_identifiers?.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-slate-500 mb-4 uppercase tracking-wider">
                    Context Identifiers
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {props.context_identifiers.map((id, index) => (
                      <Badge
                        key={index}
                        variant="outline"
                        className="text-xs bg-slate-700/50 border-slate-600/50 text-slate-300 hover:bg-slate-700"
                      >
                        {id}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              {props.modify_identifiers?.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-slate-500 mb-4 uppercase tracking-wider">
                    Modify Identifiers
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {props.modify_identifiers.map((id, index) => (
                      <Badge
                        key={index}
                        variant="outline"
                        className="text-xs bg-slate-700/50 border-slate-600/50 text-slate-300 hover:bg-slate-700"
                      >
                        {id}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </CardContent>
      )}
    </Card>
  );
}
