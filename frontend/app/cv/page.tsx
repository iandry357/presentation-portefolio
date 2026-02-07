'use client';

import { useState } from 'react';
import { getPdfUrl } from '@/lib/api';
import { Download, ChevronLeft, ChevronRight, ZoomIn, ZoomOut } from 'lucide-react';
import Image from 'next/image';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const TOTAL_PAGES = 2;

export default function CVPage() {
  const pdfUrl = getPdfUrl();
  const [currentPage, setCurrentPage] = useState(1);
  const [zoom, setZoom] = useState(100);

  return (
    <div className="container mx-auto px-4 py-8 max-w-6xl">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">
          Curriculum Vitae
        </h1>
        <a
          href={pdfUrl.replace('/view', '/download')}
          download
          className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors"
        >
          <Download className="w-4 h-4" />
          Télécharger PDF
        </a>
      </div>

      {/* Controls */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 mb-4">
        <div className="flex items-center justify-between">
          {/* Navigation pages */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
              disabled={currentPage <= 1}
              className="p-2 rounded hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronLeft className="w-5 h-5" />
            </button>
            <span className="text-sm text-gray-700 min-w-[100px] text-center font-medium">
              Page {currentPage} / {TOTAL_PAGES}
            </span>
            <button
              onClick={() => setCurrentPage(Math.min(TOTAL_PAGES, currentPage + 1))}
              disabled={currentPage >= TOTAL_PAGES}
              className="p-2 rounded hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronRight className="w-5 h-5" />
            </button>
          </div>

          {/* Zoom */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setZoom(Math.max(50, zoom - 25))}
              className="p-2 rounded hover:bg-gray-100 transition-colors"
            >
              <ZoomOut className="w-5 h-5" />
            </button>
            <span className="text-sm text-gray-700 min-w-[70px] text-center font-medium">
              {zoom}%
            </span>
            <button
              onClick={() => setZoom(Math.min(200, zoom + 25))}
              className="p-2 rounded hover:bg-gray-100 transition-colors"
            >
              <ZoomIn className="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>

      {/* Image CV */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-8 flex justify-center overflow-auto">
        <div style={{ width: `${zoom}%`, transition: 'width 0.2s ease' }}>
          <img
            src={`${API_URL}/api/cv/page/${currentPage}`}
            alt={`CV Page ${currentPage}`}
            className="w-full h-auto shadow-lg"
            loading="eager"
          />
        </div>
      </div>

      {/* Note */}
      {/* <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
        <p className="text-sm text-blue-800">
          💡 <span className="font-semibold">Astuce :</span> Les sources du chat
          pointent vers les sections correspondantes du CV.
        </p>
      </div> */}
    </div>
  );
}