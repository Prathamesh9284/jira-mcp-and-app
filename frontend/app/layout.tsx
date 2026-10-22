import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import Sidebar from "@/components/Sidebar";
import HealthBanner from "@/components/HealthBanner";
import { ToastProvider } from "@/components/Toast";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Jira Automation",
  description: "Anchanto Parcel Tracking — Jira automation tool",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full`}>
      <body className="h-full flex bg-bg text-ink antialiased">
        <ToastProvider>
          <Sidebar />
          <div className="flex-1 flex flex-col min-w-0">
            <HealthBanner />
            <main className="flex-1 overflow-y-auto p-8">{children}</main>
          </div>
        </ToastProvider>
      </body>
    </html>
  );
}
