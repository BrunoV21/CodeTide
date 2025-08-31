import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { ChevronDown, ChevronRight } from "lucide-react"
import { useState } from "react"

export default function ReasoningMessage() {
    const [isExpanded, setIsExpanded] = useState(props.defaultExpanded !== false);

    const toggleExpanded = () => {
        setIsExpanded(!isExpanded);
    };

    // Get data from props
    const reasoning = props.reasoning || "No reasoning provided";
    const data = props.data || {};
    const title = props.title || "Analysis Result";
    const summaryText = props.summaryText || "Click to view details";

    // Convert data object to array and take first two entries
    const dataEntries = Object.entries(data).slice(0, 2);

    // Generate HTML content
    const generateHtml = () => {
        let html = `
        <div class="reasoning-message">
            <div class="p-4 space-y-4">
                <div class="reasoning-block text-sm text-muted-foreground bg-muted/30 p-3 rounded-md">
                    ${reasoning}
                </div>`;

        // Add key-value entries if they exist
        if (dataEntries.length > 0) {
            html += `<div class="data-entries space-y-3">`;
            
            dataEntries.forEach(([key, value], index) => {
                html += `
                <div class="entry-block">
                    <h5 class="font-medium text-sm mb-1 text-foreground">${key}</h5>
                    <div class="text-sm text-muted-foreground bg-background p-2 rounded border">
                        ${typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value)}
                    </div>
                </div>`;
            });
            
            html += `</div>`;
        }

        html += `
                </div>
        </div>`;

        return html;
    };

    return (
        <div className="w-full">
            <div className="flex justify-between items-center mb-2">
                <h3 className="text-sm font-medium text-muted-foreground">{title}</h3>
                <TooltipProvider>
                    <Tooltip>
                        <TooltipTrigger asChild>
                            <Button 
                                size="sm" 
                                variant="outline" 
                                onClick={toggleExpanded}
                                className="h-6 px-2"
                            >
                                {isExpanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                            </Button>
                        </TooltipTrigger>
                        <TooltipContent>
                            <p>{summaryText}</p>
                        </TooltipContent>
                    </Tooltip>
                </TooltipProvider>
            </div>
            
            <Card className="w-full">
                <CardContent className="p-0">
                    {isExpanded && (
                        <div 
                            className="prose prose-sm max-w-none dark:prose-invert"
                            dangerouslySetInnerHTML={{ 
                                __html: generateHtml() 
                            }}
                        />
                    )}
                </CardContent>
            </Card>

            <style jsx>{`
                .reasoning-message pre {
                    white-space: pre-wrap;
                    word-wrap: break-word;
                }
            `}</style>
        </div>
    );
}