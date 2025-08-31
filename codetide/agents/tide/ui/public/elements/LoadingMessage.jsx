import { useState, useEffect } from "react"

export default function LoadingMessages() {
    const defaultMessages = [
        "Working",
        "Syncing CodeTide",
        "Thinking", 
        "Looking for context"
    ];
    
    const messages = props.messages || defaultMessages;
    const interval = props.interval || 2000; // 2 seconds default
    const showIcon = props.showIcon !== false; // default true
    
    const [currentMessageIndex, setCurrentMessageIndex] = useState(0);
    
    useEffect(() => {
        const timer = setInterval(() => {
            setCurrentMessageIndex((prevIndex) => 
                (prevIndex + 1) % messages.length
            );
        }, interval);
        
        return () => clearInterval(timer);
    }, [messages.length, interval]);
    
    return (
        <div className="flex items-center gap-3 p-3" style={{ fontFamily: 'Inter, sans-serif' }}>
            {showIcon && (
                <div className="flex space-x-1.5 items-center">
                    <div className="w-3 h-3 bg-primary rounded-full animate-wave-1"></div>
                    <div className="w-3 h-3 bg-primary rounded-full animate-wave-2"></div>
                    <div className="w-3 h-3 bg-primary rounded-full animate-wave-3"></div>
                </div>
            )}
            
            <span className="text-base text-muted-foreground font-medium min-w-0 transition-opacity duration-300" style={{ fontFamily: 'Inter, sans-serif' }}>
                {messages[currentMessageIndex]}...
            </span>
            
            <style jsx>{`
                @keyframes wave {
                    0%, 40%, 100% {
                        transform: translateY(0);
                    }
                    20% {
                        transform: translateY(-10px);
                    }
                }
                
                .animate-wave-1 {
                    animation: wave 1.4s ease-in-out infinite;
                }
                
                .animate-wave-2 {
                    animation: wave 1.4s ease-in-out infinite;
                    animation-delay: 0.16s;
                }
                
                .animate-wave-3 {
                    animation: wave 1.4s ease-in-out infinite;
                    animation-delay: 0.32s;
                }
            `}</style>
        </div>
    );
}