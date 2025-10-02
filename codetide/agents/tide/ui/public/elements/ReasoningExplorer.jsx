import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { ChevronDown, ChevronRight, Loader2, Brain, FileText, Edit } from "lucide-react"
import { useState } from "react"
import { cn } from "@/lib/utils"

export default function ReasoningStepsCard() {
  // Set default values for props
//   const {
//     reasoning_steps = [],
//     context_identifiers = [],
//     modify_identifiers = [],
//     finished = false
//   } = props;

  const [expandedSteps, setExpandedSteps] = useState({});
  const [expandedContext, setExpandedContext] = useState(false);
  const [expandedModify, setExpandedModify] = useState(false);
  const [expandedAll, setExpandedAll] = useState(!props.finished);

  const toggleStep = (index) => {
    setExpandedSteps(prev => ({
      ...prev,
      [index]: !prev[index]
    }));
  };

  const toggleContext = () => {
    setExpandedContext(!expandedContext);
  };

  const toggleModify = () => {
    setExpandedModify(!expandedModify);
  };

  const toggleAll = () => {
    setExpandedAll(!expandedAll);
  };

  // Check if all props are empty or undefined
  const hasNoData = (
    props.reasoning_steps.length === 0 &&
    props.context_identifiers.length === 0 &&
    props.modify_identifiers.length === 0
  );

  // If no data, show loading animation
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
      <CardHeader className="pb-2">
        <div className="flex justify-between items-center">
          <CardTitle className="text-lg font-medium">
            Reasoning Process
          </CardTitle>
          <div className="flex items-center gap-2">
            {props.finished && (
              <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">
                Completed
              </Badge>
            )}
            <button onClick={toggleAll} className="p-1 hover:bg-gray-100 rounded">
              {expandedAll ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
            </button>
          </div>
        </div>
      </CardHeader>
      {expandedAll && (
        <CardContent className="space-y-4">
          {/* Reasoning Steps */}
          {props.reasoning_steps.length > 0 && (
            <div className="space-y-4">
              {props.reasoning_steps.map((step, index) => (
                <div key={index} className="relative">
                  {index < props.reasoning_steps.length - 1 && (
                    <div className="absolute left-6 top-12 h-12 w-0.5 bg-gray-200"></div>
                  )}
                  <Card className="relative">
                    <CardHeader className="pb-2">
                      <div className="flex items-start gap-2">
                        <div className="flex-shrink-0 w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center">
                          <Brain className="h-5 w-5 text-blue-600" />
                        </div>
                        <div className="flex-1">
                          <CardTitle className="text-base font-medium">
                            {step.header}
                          </CardTitle>
                        </div>
                        <button 
                          onClick={() => toggleStep(index)} 
                          className="p-1 hover:bg-gray-100 rounded"
                        >
                          {expandedSteps[index] ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                        </button>
                      </div>
                    </CardHeader>
                    <CardContent className="pt-0">
                      <p className="text-sm text-gray-700 mb-2">{step.content}</p>
                      {expandedSteps[index] && step.candidate_identifiers && step.candidate_identifiers.length > 0 && (
                        <div className="mt-2 p-2 bg-gray-50 rounded">
                          <p className="text-xs font-medium text-gray-500 mb-1">Candidate Identifiers:</p>
                          <div className="flex flex-wrap gap-1">
                            {step.candidate_identifiers.map((id, idIndex) => (
                              <Badge key={idIndex} variant="outline" className="text-xs">
                                {id}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                </div>
              ))}
            </div>
          )}

          {/* Context Identifiers */}
          {props.context_identifiers.length > 0 && (
            <Card>
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <FileText className="h-5 w-5 text-gray-600" />
                    <CardTitle className="text-base font-medium">
                      Context Identifiers
                    </CardTitle>
                  </div>
                  <button 
                    onClick={toggleContext} 
                    className="p-1 hover:bg-gray-100 rounded"
                  >
                    {expandedContext ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                  </button>
                </div>
              </CardHeader>
              {expandedContext && (
                <CardContent className="pt-0">
                  <div className="flex flex-wrap gap-1">
                    {props.context_identifiers.map((id, index) => (
                      <Badge key={index} variant="outline" className="text-xs">
                        {id}
                      </Badge>
                    ))}
                  </div>
                </CardContent>
              )}
            </Card>
          )}

          {/* Modify Identifiers */}
          {props.modify_identifiers.length > 0 && (
            <Card>
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Edit className="h-5 w-5 text-gray-600" />
                    <CardTitle className="text-base font-medium">
                      Modify Identifiers
                    </CardTitle>
                  </div>
                  <button 
                    onClick={toggleModify} 
                    className="p-1 hover:bg-gray-100 rounded"
                  >
                    {expandedModify ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                  </button>
                </div>
              </CardHeader>
              {expandedModify && (
                <CardContent className="pt-0">
                  <div className="flex flex-wrap gap-1">
                    {props.modify_identifiers.map((id, index) => (
                      <Badge key={index} variant="outline" className="text-xs">
                        {id}
                      </Badge>
                    ))}
                  </div>
                </CardContent>
              )}
            </Card>
          )}
        </CardContent>
      )}
    </Card>
  );
}