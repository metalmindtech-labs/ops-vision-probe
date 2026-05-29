import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Dashboard from "@/pages/Dashboard";
import { Toaster } from "@/components/ui/sonner";

function App() {
    return (
        <div className="App dark">
            <BrowserRouter>
                <Routes>
                    <Route path="/" element={<Dashboard />} />
                </Routes>
            </BrowserRouter>
            <Toaster
                position="bottom-right"
                theme="dark"
                toastOptions={{
                    classNames: {
                        toast:
                            "!bg-zinc-950 !border !border-lime-400/30 !text-zinc-100 !font-mono",
                        title: "!text-zinc-50",
                        description: "!text-zinc-400",
                    },
                }}
            />
        </div>
    );
}

export default App;
