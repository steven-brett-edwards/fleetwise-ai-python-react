"""RAG pipeline: chunker, embeddings, vector store, ingestion.

The layers line up one-to-one with the .NET edition's
`Services/DocumentChunker.cs` + `Services/DocumentIngestionService.cs` +
`Plugins/DocumentSearchPlugin.cs` split. Kept modular so Phase 10's
ETL pipeline can reuse the chunker over inspection-note documents
without pulling the whole stack.
"""
