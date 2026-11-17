// Entry point: mounts the chat page into the #root element of index.html

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { ChatPage } from "./ChatPage";
import "./chatPage.css";


createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ChatPage />
  </StrictMode>,
);
