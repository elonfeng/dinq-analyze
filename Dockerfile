# Build stage
FROM golang:1.25.0-alpine AS builder

WORKDIR /app

# Install dependencies
RUN apk add --no-cache git ca-certificates

# Copy go mod files
COPY go.mod go.sum ./

# Copy source code
COPY . .

# Download dependencies and build
RUN go mod tidy && CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o server ./cmd/server

# Runtime stage
FROM alpine:3.19

WORKDIR /app

# Install ca-certificates for HTTPS
RUN apk --no-cache add ca-certificates tzdata

# Copy binary from builder
COPY --from=builder /app/server .

# Copy data files (CSV for role models/celebrities)
COPY --from=builder /app/data ./data
COPY --from=builder /app/*.csv ./

# Set timezone
ENV TZ=Asia/Shanghai

# Expose port
EXPOSE 8080

# Run
CMD ["./server"]
