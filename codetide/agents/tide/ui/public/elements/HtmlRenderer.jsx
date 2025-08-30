import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { X, RefreshCw } from "lucide-react"

export default function HtmlRenderer() {
    // Function to sanitize HTML (basic approach)
    const sanitizeHtml = (html) => {
        // Create a temporary div to parse the HTML
        const temp = document.createElement('div');
        temp.innerHTML = html;
        
        // Remove potentially dangerous elements
        const dangerousElements = temp.querySelectorAll('script, object, embed, iframe');
        dangerousElements.forEach(el => el.remove());
        
        return temp.innerHTML;
    };

    const handleRefresh = () => {
        // Re-render the component by updating props
        updateElement(props);
    };

    const handleRemove = () => {
        deleteElement();
    };

    // Get the HTML content from props
    const htmlContent = props.html || props.content || '<p>No HTML content provided</p>';
    const title = props.title || 'HTML Content';
    const showControls = props.showControls !== false; // Default to true

    return (
        <div className="w-full">
            {showControls && (
                <div className="flex justify-between items-center mb-2">
                    <h3 className="text-sm font-medium text-muted-foreground">{title}</h3>
                    <div className="flex gap-1">
                        <Button 
                            size="sm" 
                            variant="outline" 
                            onClick={handleRefresh}
                            className="h-6 px-2"
                        >
                            <RefreshCw className="h-3 w-3" />
                        </Button>
                        <Button 
                            size="sm" 
                            variant="outline" 
                            onClick={handleRemove}
                            className="h-6 px-2"
                        >
                            <X className="h-3 w-3" />
                        </Button>
                    </div>
                </div>
            )}
            
            <Card className="w-full">
                <CardContent className="p-4">
                    <div 
                        className="prose prose-sm max-w-none dark:prose-invert"
                        dangerouslySetInnerHTML={{ 
                            __html: sanitizeHtml(htmlContent) 
                        }}
                    />
                </CardContent>
            </Card>
        </div>
    );
}