import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ChevronDown, ChevronRight, Layers, Brain } from "lucide-react";
import { useState, useEffect } from "react";

export default function ReasoningStepsCard() {
  const [expandedSteps, setExpandedSteps] = useState({});
  const [expandedAll, setExpandedAll] = useState(true);
  const [expandedIdentifiers, setExpandedIdentifiers] = useState(false);
  const [waveOffset, setWaveOffset] = useState(0);
  const [loadingText, setLoadingText] = useState("Analyzing");
  const [thinkingTime, setThinkingTime] = useState(0);

  const loadingStates = ["Analyzing", "Thinking", "Updating", "Processing"];

  // Animate wave effect and loading text
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

  // Track thinking time
  useEffect(() => {
    if (!props.finished) {
      const timer = setInterval(() => {
        setThinkingTime((prev) => prev + 1);
      }, 1000);
      return () => clearInterval(timer);
    }
  }, [props.finished]);

  const toggleStep = (index) => {
    setExpandedSteps((prev) => ({
      ...prev,
      [index]: !prev[index],
    }));
  };

  const toggleAll = () => {
    setExpandedAll(!expandedAll);
  };

  const toggleIdentifiers = () => {
    setExpandedIdentifiers(!expandedIdentifiers);
  };

  const hasNoData =
    props.reasoning_steps.length === 0 &&
    props.context_identifiers.length === 0 &&
    props.modify_identifiers.length === 0;

  const isLoadingState = !props.finished && !props.summary;

  if (hasNoData && !props.finished) {
    return (
      <Card className="w-full bg-gradient-to-b from-slate-900 to-slate-950 border-slate-800">
        <CardContent className="flex flex-col items-center justify-center py-12 px-6">
          <svg className="w-8 h-8 mb-4 opacity-60" viewBox="0 0 100 100">
            <defs>
              <style>{`
                @keyframes wave {
                  0%, 100% { 
                    d: path('M0,50 Q25,${25 + Math.sin(waveOffset * Math.PI / 180) * 15},50,50 T100,50'); 
                  }
                  50% { 
                    d: path('M0,50 Q25,${75 - Math.sin((180 + waveOffset) * Math.PI / 180) * 15},50,50 T100,50'); 
                  }
                }
                .wave-line { 
                  fill: none; 
                  stroke: rgb(96, 165, 250); 
                  stroke-width: 2; 
                  animation: wave 3s ease-in-out infinite; 
                }
              `}</style>
            </defs>
            <path d="M0,50 Q25,40,50,50 T100,50" className="wave-line" strokeLinecap="round" />
            <path d="M0,60 Q25,50,50,60 T100,60" className="wave-line" strokeLinecap="round" style={{animationDelay: '0.2s', opacity: 0.6}} />
          </svg>
          <span className="text-slate-400 text-sm">{loadingText}...</span>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="w-full bg-gradient-to-b from-slate-900 to-slate-950 border-slate-800">
      {/* Header */}
      <CardHeader className="px-6 py-4 border-b border-slate-700/50">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            {isLoadingState ? (
              <div className="flex items-center gap-3">
                <svg className="w-5 h-5 opacity-60 flex-shrink-0" viewBox="0 0 100 60">
                  <defs>
                    <style>{`
                      @keyframes wave-motion {
                        0%, 100% { d: path('M0,30 Q25,${15 + Math.sin(0 * Math.PI / 180) * 12},50,30 T100,30 L100,60 L0,60'); }
                        50% { d: path('M0,30 Q25,${45 - Math.sin(180 * Math.PI / 180) * 12},50,30 T100,30 L100,60 L0,60'); }
                      }
                      .wave-fill { fill: url(#waveGradient); animation: wave-motion 3s ease-in-out infinite; }
                    `}</style>
                    <linearGradient id="waveGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                      <stop offset="0%" stopColor="rgb(96, 165, 250)" stopOpacity="0.5" />
                      <stop offset="100%" stopColor="rgb(96, 165, 250)" stopOpacity="0.1" />
                    </linearGradient>
                  </defs>
                  <path d="M0,30 Q25,20,50,30 T100,30 L100,60 L0,60" className="wave-fill" />
                </svg>
                <span className="text-slate-400 text-sm">{loadingText}...</span>
              </div>
            ) : (
              <div className="space-y-2">
                <p className="text-xs text-slate-500 font-medium">Thought for {thinkingTime}s</p>
                <p className="text-sm text-slate-200 leading-relaxed line-clamp-1">
                  {props.summary}
                </p>
              </div>
            )}
          </div>
          <button
            onClick={toggleAll}
            className="p-1 hover:bg-slate-700 rounded transition flex-shrink-0 mt-0.5"
            aria-label="Toggle details"
          >
            {expandedAll ? (
              <ChevronDown className="h-4 w-4 text-slate-400" />
            ) : (
              <ChevronRight className="h-4 w-4 text-slate-400" />
            )}
          </button>
        </div>
      </CardHeader>

      {/* Content */}
      {expandedAll && (
        <CardContent className="px-6 py-6">
          {/* Reasoning Steps */}
          {props.reasoning_steps.map((step, index) => (
            <div key={index}>
              <div className="relative flex gap-4">
                {/* Timeline */}
                <div className="flex flex-col items-center pt-0.5 flex-shrink-0">
                  <div className="w-6 h-6 rounded-full bg-blue-500/20 border border-blue-500/40 flex items-center justify-center">
                    <Brain className="w-3 h-3 text-blue-400" />
                  </div>
                </div>

                {/* Content */}
                <div className="flex-1 pt-0.5">
                  <div className="flex items-start justify-between gap-3 mb-2">
                    <div className="flex-1 min-w-0">
                      <h3 className="text-sm font-semibold text-slate-100 mb-2">
                        {step.header}
                      </h3>
                      <p className="text-xs text-slate-400 leading-relaxed">
                        {step.content}
                      </p>
                    </div>
                    {step.candidate_identifiers?.length > 0 && (
                      <button
                        onClick={() => toggleStep(index)}
                        className="p-1 hover:bg-slate-700 rounded flex-shrink-0 transition"
                        aria-label="Toggle identifiers"
                      >
                        {expandedSteps[index] ? (
                          <ChevronDown className="h-4 w-4 text-slate-500" />
                        ) : (
                          <ChevronRight className="h-4 w-4 text-slate-500" />
                        )}
                      </button>
                    )}
                  </div>

                  {/* Identifiers */}
                  {expandedSteps[index] && step.candidate_identifiers?.length > 0 && (
                    <div className="mt-4 p-3 bg-slate-800/30 border border-slate-700/50 rounded">
                      <p className="text-xs font-medium text-slate-500 mb-3">
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

              {/* Connector line - only between steps */}
              {index < props.reasoning_steps.length - 1 && (
                <div className="relative flex gap-4 mt-6">
                  <div className="w-6 flex justify-center flex-shrink-0">
                    <div className="w-px bg-gradient-to-b from-orange-500 to-transparent" style={{ height: "28px" }}></div>
                  </div>
                </div>
              )}
            </div>
          ))}

          {/* Deep Analysis */}
          {(props.context_identifiers.length > 0 ||
            props.modify_identifiers.length > 0) && (
            <div className="mt-6 pt-6 border-t border-slate-700/50">
              <button
                onClick={toggleIdentifiers}
                className="w-full flex items-center justify-between px-0 py-2 hover:bg-slate-800/30 rounded transition group text-left"
              >
                <span className="text-sm font-semibold text-slate-300 group-hover:text-slate-100">
                  Deeper Analysis
                </span>
                <svg className={`w-4 h-4 text-slate-500 transition-transform flex-shrink-0 ${expandedIdentifiers ? 'rotate-180' : ''}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <polyline points="6 9 12 15 18 9"></polyline>
                </svg>
              </button>

              {expandedIdentifiers && (
                <div className="mt-4 p-4 bg-slate-800/20 border border-slate-700/30 rounded-lg space-y-6">
                  {/* Context Identifiers */}
                  {props.context_identifiers.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-slate-500 mb-3 uppercase tracking-wider">
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

                  {/* Divider */}
                  {props.context_identifiers.length > 0 && props.modify_identifiers.length > 0 && (
                    <div className="border-t border-slate-700/30"></div>
                  )}

                  {/* Modify Identifiers */}
                  {props.modify_identifiers.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-slate-500 mb-3 uppercase tracking-wider">
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
            </div>
          )}
        </CardContent>
      )}
    </Card>
  );
}
