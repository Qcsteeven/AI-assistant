FROM node:18-alpine

WORKDIR /app

# Сначала копируем только package.json
COPY package.json .

# Проверяем валидность package.json
RUN npm install --dry-run

# Копируем остальные файлы
COPY . .

RUN npm install

EXPOSE 3000

CMD ["npm", "start"]