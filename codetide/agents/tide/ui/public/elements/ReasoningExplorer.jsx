import { Card, CardHeader, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Brain } from "lucide-react";
import { useState, useEffect } from "react";

export default function ReasoningStepsCard() {
  const [waveOffset, setWaveOffset] = useState(0);
  const [loadingText, setLoadingText] = useState("Analyzing");
  const [thinkingTime, setThinkingTime] = useState(0);

  const loadingStates = ["Analyzing", "Thinking", "Updating", "Processing"];
  const isLoadingState = !props?.finished;

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
    if (!props?.finished) {
      const timer = setInterval(() => {
        setThinkingTime((prev) => prev + 1);
      }, 1000);
      return () => clearInterval(timer);
    }
  }, [props?.finished]);

  const getPreviewText = () => {
    if (props?.summary) return props.summary.split("\n")[0];
    if (props?.reasoning_steps?.length > 0)
      return props.reasoning_steps.at(-1).content.split("\n")[0];
    if (props?.finished) return "Finished";
    return `${loadingText}...`;
  };

  const previewText = getPreviewText();

  return (
    <Card className="w-full bg-gradient-to-b from-slate-900 to-slate-950 border-slate-800 transition-all duration-300">
      {/* Header */}
      <CardHeader className="px-8 py-6 border-b border-slate-700/50">
        <div className="flex items-start gap-4">
          {isLoadingState && (
            <svg
              className="w-5 h-5 opacity-60 flex-shrink-0 mt-1"
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
                  <stop offset="0%" stopColor="rgb(96,165,250)" stopOpacity="0.5" />
                  <stop offset="100%" stopColor="rgb(96,165,250)" stopOpacity="0.1" />
                </linearGradient>
              </defs>
              <path
                d="M0,30 Q25,20,50,30 T100,30 L100,60 L0,60"
                className="wave-fill"
              />
            </svg>
          )}

          <div className="flex-1">
            {props?.finished && (
              <p className="text-xs text-slate-500 font-medium mb-2 tracking-wide">
                Thought for {thinkingTime}s
              </p>
            )}
            <p className="text-slate-100 text-base leading-relaxed font-medium">
              {previewText}
            </p>
          </div>
        </div>
      </CardHeader>

      {/* Main Content */}
      <CardContent className="px-8 py-8 space-y-10">
        {/* Reasoning Steps */}
        {props?.reasoning_steps?.length > 0 && (
          <div className="space-y-2">
            {props.reasoning_steps.map((step, index) => (
              <div key={index} className="relative flex gap-6">
                {/* Timeline Column */}
                <div className="flex flex-col items-center flex-shrink-0 relative pt-1">
                  <div 
                    className="w-7 h-7 rounded-full bg-slate-950 border border-blue-500/40 flex items-center justify-center relative z-10 flex-shrink-0 shadow-lg"
                    style={{background: "hsl(216, 100%, 10%)"}}
                  >
                    <div className="absolute inset-0 rounded-full bg-blue-500/20"></div>
                    <Brain className="w-3.5 h-3.5 text-blue-300 relative z-10" />
                  </div>
                  
                  {/* Vertical connector line */}
                  {index < props.reasoning_steps.length - 1 && (
                    <svg 
                      className="absolute top-7 left-1/2 transform -translate-x-1/2 w-0.5 pointer-events-none flex-shrink-0" 
                      style={{ height: "120px" }} 
                      viewBox="0 0 2 80" 
                      preserveAspectRatio="none"
                    >
                      <line x1="1" y1="0" x2="1" y2="80" stroke="#334155" strokeWidth="1" opacity="0.6" />
                    </svg>
                  )}
                </div>

                {/* Step Content */}
                <div className="flex-1 pt-1 pb-4">
                  <h3 className="text-sm font-semibold text-slate-50 mb-3 tracking-tight">
                    {step.header}
                  </h3>
                  <p className="text-sm text-slate-400 leading-relaxed mb-4">
                    {step.content}
                  </p>

                  {/* Candidate Identifiers */}
                  {step.candidate_identifiers?.length > 0 && (
                    <div className="flex flex-wrap gap-2 pt-2">
                      {step.candidate_identifiers.map((id, idIndex) => (
                        <Badge
                          key={idIndex}
                          variant="outline"
                          className="text-xs bg-slate-800/60 border-slate-600/60 text-slate-300 hover:bg-slate-700/80 hover:text-slate-200 rounded-md px-2.5 py-1 transition-colors"
                        >
                          {id}
                        </Badge>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Context + Modify Identifiers */}
        {(props?.context_identifiers?.length > 0 ||
          props?.modify_identifiers?.length > 0) && (
          <div className="pt-10 border-t border-slate-700/30 space-y-8">
            {props.context_identifiers?.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-4 pl-0.5">Context Identifiers</p>
                <div className="flex flex-wrap gap-2" style={{marginTop: "1rem", marginBottom: "1rem"}}>
                  {props.context_identifiers.map((id, index) => (
                    <Badge
                      key={index}
                      variant="outline"
                      className="text-xs bg-slate-800/60 border-slate-600/60 text-slate-300 hover:bg-slate-700/80 hover:text-slate-200 rounded-md px-2.5 py-1.5 transition-colors"
                    >
                      {id}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {props.modify_identifiers?.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-4 pl-0.5">Modification Identifiers</p>
                <div className="flex flex-wrap gap-2">
                  {props.modify_identifiers.map((id, index) => (
                    <Badge
                      key={index}
                      variant="outline"
                      className="text-xs bg-slate-800/60 border-slate-600/60 text-slate-300 hover:bg-slate-700/80 hover:text-slate-200 rounded-md px-2.5 py-1.5 transition-colors"
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
    </Card>
  );
}