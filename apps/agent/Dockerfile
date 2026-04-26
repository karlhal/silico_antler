FROM node:20-alpine AS build

WORKDIR /app

COPY package.json ./
RUN npm install

COPY . .
RUN npm run build

FROM nginx:1.27-alpine

# Create the agent subdirectory to match the /agent/ base path
RUN mkdir -p /usr/share/nginx/html/agent
COPY --from=build /app/dist /usr/share/nginx/html/agent

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
