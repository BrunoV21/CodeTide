import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ChevronDown, ChevronRight, Loader2, Brain, Layers } from "lucide-react";
import { useState } from "react";

export default function ReasoningStepsCard() {
  const [expandedSteps, setExpandedSteps] = useState({});
  const [expandedAll, setExpandedAll] = useState(!props.finished);
  const [expandedIdentifiers, setExpandedIdentifiers] = useState(false);

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

  if (hasNoData) {
    return (
      <Card className="w-full max-w-2xl">
        <CardContent className="flex items-center justify-center py-8">
          <div className="flex items-center gap-2">
            <Loader2 className="h-6 w-6 animate-spin" />
            <span>Analyzing...</span>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="w-full max-w-2xl">
      {/* Header */}
      <CardHeader className="pb-6">
        <div className="flex justify-between items-center">
          <div className="flex items-center gap-2">
            <CardTitle className="text-lg font-medium">
              Reasoning Process
            </CardTitle>
            {!props.finished && (
              <Loader2 className="h-4 w-4 animate-spin text-blue-600" />
            )}
          </div>
          <button
            onClick={toggleAll}
            className="p-1 hover:bg-gray-100 rounded transition"
          >
            {expandedAll ? (
              <ChevronDown className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            )}
          </button>
        </div>
      </CardHeader>

      {/* Timeline */}
      {expandedAll && (
        <CardContent className="space-y-6">
          {/* Reasoning Steps */}
          {props.reasoning_steps.map((step, index) => (
            <div key={index} className="relative flex gap-6">
              {/* Timeline Icon + Connector */}
              <div className="flex flex-col items-center pt-2">
                <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0">
                  <Brain className="w-4 h-4 text-blue-600" />
                </div>
                {index < props.reasoning_steps.length - 1 && (
                  <div
                    className="w-0.5 bg-gray-300 flex-grow mt-2"
                    style={{ minHeight: "40px" }}
                  ></div>
                )}
              </div>

              {/* Step Content */}
              <div className="flex-1 pt-0.5">
                <div className="flex items-start justify-between gap-2 mb-2">
                  <div className="flex-1">
                    <h3 className="text-sm font-semibold text-gray-900 mb-1">
                      {step.header}
                    </h3>
                    <p className="text-sm text-gray-600 leading-relaxed">
                      {step.content}
                    </p>
                  </div>
                  <button
                    onClick={() => toggleStep(index)}
                    className="p-1 hover:bg-gray-100 rounded flex-shrink-0"
                  >
                    {expandedSteps[index] ? (
                      <ChevronDown className="h-4 w-4" />
                    ) : (
                      <ChevronRight className="h-4 w-4" />
                    )}
                  </button>
                </div>

                {/* Expanded candidate identifiers */}
                {expandedSteps[index] && step.candidate_identifiers?.length > 0 && (
                  <div className="mt-3 p-3 border border-gray-100 rounded-lg transition-all" style={{backgroundColor: 'transparent'}}>
                    <p className="text-xs font-medium text-gray-500 mb-2">
                      Candidate Identifiers:
                    </p>
                    <div className="flex flex-wrap gap-1">
                      {step.candidate_identifiers.map((id, idIndex) => (
                        <Badge
                          key={idIndex}
                          variant="outline"
                          className="text-xs bg-white/50 hover:bg-white"
                        >
                          {id}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}

          {/* Unified Context + Modify Identifiers */}
          {(props.context_identifiers.length > 0 ||
            props.modify_identifiers.length > 0) && (
            <div className="border-t pt-4 mt-4">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <Layers className="h-5 w-5 text-gray-600" />
                  <h4 className="text-base font-medium text-gray-800">
                    Additional Identifiers
                  </h4>
                </div>
                <button
                  onClick={toggleIdentifiers}
                  className="p-1 hover:bg-gray-100 rounded"
                >
                  {expandedIdentifiers ? (
                    <ChevronDown className="h-4 w-4" />
                  ) : (
                    <ChevronRight className="h-4 w-4" />
                  )}
                </button>
              </div>

              {expandedIdentifiers && (
                  <div className="mt-3 p-3 border border-gray-100 rounded-lg transition-all" style={{backgroundColor: 'transparent', marginBottom: '0.75rem'}}>
                  {/* Context Identifiers */}
                  {props.context_identifiers.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-gray-500 mb-2">
                        Context Identifiers:
                      </p>
                      <div className="flex flex-wrap gap-4" style={{margin: '0.75rem'}}>
                        {props.context_identifiers.map((id, index) => (
                          <Badge
                            key={index}
                            variant="outline"
                            className="text-xs bg-white/50 hover:bg-white"
                          >
                            {id}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Modify Identifiers */}
                  {props.modify_identifiers.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-gray-500 mb-2">
                        Modify Identifiers:
                      </p>
                      <div className="flex flex-wrap gap-1">
                        {props.modify_identifiers.map((id, index) => (
                          <Badge
                            key={index}
                            variant="outline"
                            className="text-xs bg-white/50 hover:bg-white"
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
