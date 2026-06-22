const canvas = document.getElementById('gameCanvas');
const ctx = canvas.getContext('2d');
const questionEl = document.getElementById('question');
const levelEl = document.getElementById('level');

const CELL_SIZE = 38;
const WALL_SIZE = 10;
const GRID_W = 23;
const GRID_H = 13;
canvas.width = GRID_W * CELL_SIZE + WALL_SIZE;
canvas.height = GRID_H * CELL_SIZE + WALL_SIZE;

const perguntas = [
    { pergunta: "Qual a unidade de energia no Sistema Internacional?", respostas: ["JOULE", "CALORIA", "WATT", "ERG"], correta: 0 },
    { pergunta: "Como é chamada a reação química que absorve calor?", respostas: ["ENDOTÉRMICA", "EXOTÉRMICA", "ISOTÉRMICA", "ADIABÁTICA"], correta: 0 },
    { pergunta: "O que a Entalpia mede em uma reação química?", respostas: ["CALOR TROCADO", "TEMPERATURA", "PRESSÃO", "VOLUME"], correta: 0 },
    { pergunta: "O que a Lei de Hess afirma sobre a variação de entalpia?", respostas: ["INDEPENDE DO CAMINHO", "DEPENDE DA PRESSÃO", "VARIA COM TEMPERATURA", "É SEMPRE POSITIVA"], correta: 0 },
    { pergunta: "O que o calor precisa para mudar de fase?", respostas: ["CALOR LATENTE", "CALOR SENSÍVEL", "CALOR ESPECÍFICO", "CAPACIDADE TÉRMICA"], correta: 0 }
];

let faseIndex = 0;
let jogoAtivo = false;
let animacaoId = null;
let transicaoAtiva = false;
let mensagemObjetivo = "";
let tempoMensagem = 0;

let tempoRestante = 50;
let intervaloId = null;

let labAtual = null;
let labCache = {};

const jogador = {
    x: 100, y: 100,
    largura: 22, altura: 28,
    velocidade: 7.5
};

let portaPos = { x: 0, y: 0, largura: 48, altura: 64 };
let chaveObtida = false;
let chavePos = { x: 0, y: 0, ativa: false };
let respostaColetada = false;
let portaIbu = false;

let respostasPos = [];
let paredes = [];
let gridLabirinto = null;
let celulasLivres = [];
let posInicialJogador = { x: 0, y: 0 };
let posPortaPixel = { x: 0, y: 0 };

let faseVitoria = false;
let vitoriaReiniciarArea = { x: 0, y: 0, w: 200, h: 60 };
let jogoFinalizado = false;

const teclas = {};

function criarSalaPreparacao() {
    let paredesLista = [];
    const salaX = 150, salaY = 100, salaW = 500, salaH = 400;
    const portaAltura = 64;
    const portaY = salaY + (salaH - portaAltura) / 2;
    paredesLista.push([0, 0, canvas.width, WALL_SIZE]);
    paredesLista.push([0, canvas.height - WALL_SIZE, canvas.width, WALL_SIZE]);
    paredesLista.push([0, 0, WALL_SIZE, canvas.height]);
    paredesLista.push([canvas.width - WALL_SIZE, 0, WALL_SIZE, canvas.height]);
    paredesLista.push([salaX, salaY, salaW, WALL_SIZE]);
    paredesLista.push([salaX, salaY, WALL_SIZE, salaH]);
    paredesLista.push([salaX, salaY + salaH - WALL_SIZE, salaW, WALL_SIZE]);
    const portaX = salaX + salaW - WALL_SIZE;
    if (portaY > salaY) {
        paredesLista.push([portaX, salaY, WALL_SIZE, portaY - salaY]);
    }
    if (portaY + portaAltura < salaY + salaH) {
        paredesLista.push([portaX, portaY + portaAltura, WALL_SIZE, salaY + salaH - (portaY + portaAltura)]);
    }
    let jogadorX = salaX + 60;
    let jogadorY = salaY + salaH/2 - jogador.altura/2;
    let porta = { x: portaX - 48, y: portaY, largura: 48, altura: portaAltura };
    return { paredes: paredesLista, jogadorX, jogadorY, porta };
}

function gerarLabirinto(fase) {
    let grid = Array(GRID_H).fill().map(() => Array(GRID_W).fill(true));
    function cellToPixel(col, row) {
        return { x: WALL_SIZE + col * CELL_SIZE, y: WALL_SIZE + row * CELL_SIZE };
    }
    let startCol = 1 + 2 * Math.floor(Math.random() * ((GRID_W - 2) / 2));
    let startRow = 1 + 2 * Math.floor(Math.random() * ((GRID_H - 2) / 2));
    grid[startRow][startCol] = false;
    let stack = [{ col: startCol, row: startRow }];
    const dirs = [
        { dc: 2, dr: 0, wallCol: 1, wallRow: 0 },
        { dc: -2, dr: 0, wallCol: -1, wallRow: 0 },
        { dc: 0, dr: 2, wallCol: 0, wallRow: 1 },
        { dc: 0, dr: -2, wallCol: 0, wallRow: -1 }
    ];
    while (stack.length) {
        let current = stack[stack.length - 1];
        let neighbors = [];
        for (let d of dirs) {
            let nc = current.col + d.dc;
            let nr = current.row + d.dr;
            if (nc > 0 && nc < GRID_W - 1 && nr > 0 && nr < GRID_H - 1 && grid[nr][nc] === true) {
                neighbors.push({ col: nc, row: nr, wallCol: current.col + d.wallCol, wallRow: current.row + d.wallRow });
            }
        }
        if (neighbors.length) {
            let next = neighbors[Math.floor(Math.random() * neighbors.length)];
            grid[next.row][next.col] = false;
            grid[next.wallRow][next.wallCol] = false;
            stack.push({ col: next.col, row: next.row });
        } else {
            stack.pop();
        }
    }
    let paredesLista = [];
    paredesLista.push([0, 0, canvas.width, WALL_SIZE]);
    paredesLista.push([0, canvas.height - WALL_SIZE, canvas.width, WALL_SIZE]);
    paredesLista.push([0, 0, WALL_SIZE, canvas.height]);
    paredesLista.push([canvas.width - WALL_SIZE, 0, WALL_SIZE, canvas.height]);
    for (let row = 0; row < GRID_H; row++) {
        for (let col = 0; col < GRID_W; col++) {
            if (grid[row][col]) {
                let cellX = WALL_SIZE + col * CELL_SIZE;
                let cellY = WALL_SIZE + row * CELL_SIZE;
                paredesLista.push([cellX, cellY, CELL_SIZE, CELL_SIZE]);
            }
        }
    }
    let celulasLivresLista = [];
    for (let row = 0; row < GRID_H; row++) {
        for (let col = 0; col < GRID_W; col++) {
            if (!grid[row][col]) celulasLivresLista.push({ col, row });
        }
    }
    let posInicial, posPorta;
    if (celulasLivresLista.length >= 2) {
        posInicial = celulasLivresLista[0];
        posPorta = celulasLivresLista[celulasLivresLista.length - 1];
    } else {
        posInicial = { col: 1, row: 1 };
        posPorta = { col: GRID_W - 2, row: GRID_H - 2 };
    }
    let inicioPixel = cellToPixel(posInicial.col, posInicial.row);
    let portaPixel = cellToPixel(posPorta.col, posPorta.row);
    let jogadorX = inicioPixel.x + (CELL_SIZE - jogador.largura) / 2;
    let jogadorY = inicioPixel.y + (CELL_SIZE - jogador.altura) / 2;
    if (colisaoParede(jogadorX, jogadorY, jogador.largura, jogador.altura)) {
        for (let cel of celulasLivresLista) {
            let testeX = cellToPixel(cel.col, cel.row).x + (CELL_SIZE - jogador.largura) / 2;
            let testeY = cellToPixel(cel.col, cel.row).y + (CELL_SIZE - jogador.altura) / 2;
            if (!colisaoParede(testeX, testeY, jogador.largura, jogador.altura)) {
                jogadorX = testeX;
                jogadorY = testeY;
                break;
            }
        }
    }
    return { paredes: paredesLista, portaPixel: portaPixel, jogadorX, jogadorY, celulasLivres: celulasLivresLista, grid, posInicial, posPorta };
}

function obterLabirintoFixo(fase) {
    if (labCache[fase]) {
        return JSON.parse(JSON.stringify(labCache[fase]));
    }
    const lab = gerarLabirinto(fase);
    labCache[fase] = JSON.parse(JSON.stringify(lab));
    return JSON.parse(JSON.stringify(lab));
}

function mostrarObjetivo(msg, duracao) {
    mensagemObjetivo = msg;
    tempoMensagem = Date.now() + duracao;
}

function desenharObjetivo() {
    if (Date.now() < tempoMensagem) {
        ctx.font = 'bold 20px "Courier New"';
        ctx.fillStyle = '#FFD700';
        ctx.shadowBlur = 10;
        ctx.shadowColor = '#000';
        ctx.textAlign = 'center';
        ctx.fillText(mensagemObjetivo, canvas.width / 2, 45);
    }
}

function encontrarCaminhoCelulas(posInicial, posPorta, celulasLivresLista) {
    let visitados = new Set();
    let fila = [{ col: posInicial.col, row: posInicial.row, caminho: [posInicial] }];
    while (fila.length > 0) {
        let atual = fila.shift();
        let key = `${atual.col},${atual.row}`;
        if (visitados.has(key)) continue;
        visitados.add(key);
        if (atual.col === posPorta.col && atual.row === posPorta.row) {
            return atual.caminho;
        }
        const dirs = [[0, -1], [0, 1], [-1, 0], [1, 0]];
        for (let d of dirs) {
            let nc = atual.col + d[0];
            let nr = atual.row + d[1];
            let celulaExiste = celulasLivresLista.some(c => c.col === nc && c.row === nr);
            if (celulaExiste && !visitados.has(`${nc},${nr}`)) {
                fila.push({ col: nc, row: nr, caminho: [...atual.caminho, { col: nc, row: nr }] });
            }
        }
    }
    return [posInicial, posPorta];
}

function posicionarRespostasEmBecos(celulasLivresLista, posInicial, posPorta) {
    if (!celulasLivresLista || celulasLivresLista.length < 4) return [];
    let caminhoPrincipal = encontrarCaminhoCelulas(posInicial, posPorta, celulasLivresLista);
    let celulasCaminho = new Set(caminhoPrincipal.map(c => `${c.col},${c.row}`));
    let becos = celulasLivresLista.filter(cel => {
        if (celulasCaminho.has(`${cel.col},${cel.row}`)) return false;
        let vizinhosLivre = 0;
        const dirs = [[0, -1], [0, 1], [-1, 0], [1, 0]];
        for (let d of dirs) {
            let nc = cel.col + d[0];
            let nr = cel.row + d[1];
            let celulaExiste = celulasLivresLista.some(c => c.col === nc && c.row === nr);
            if (celulaExiste) vizinhosLivre++;
        }
        return vizinhosLivre === 1;
    });
    if (becos.length < 4) {
        becos = celulasLivresLista.filter(cel => !celulasCaminho.has(`${cel.col},${cel.row}`));
    }
    let melhorSelecao = null;
    let melhorDistanciaMinima = 0;
    for (let tentativa = 0; tentativa < 50 && becos.length >= 4; tentativa++) {
        let embaralhados = [...becos];
        for (let i = embaralhados.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [embaralhados[i], embaralhados[j]] = [embaralhados[j], embaralhados[i]];
        }
        let selected = embaralhados.slice(0, 4);
        let distanciaMinima = Infinity;
        for (let i = 0; i < selected.length; i++) {
            for (let j = i + 1; j < selected.length; j++) {
                let dist = Math.abs(selected[i].col - selected[j].col) + Math.abs(selected[i].row - selected[j].row);
                if (dist < distanciaMinima) distanciaMinima = dist;
            }
        }
        if (distanciaMinima > melhorDistanciaMinima) {
            melhorDistanciaMinima = distanciaMinima;
            melhorSelecao = [...selected];
        }
        if (distanciaMinima >= 7) break;
    }
    let selected = melhorSelecao || becos.slice(0, 4);
    let posicoes = selected.map(cel => ({
        x: WALL_SIZE + cel.col * CELL_SIZE + CELL_SIZE/2,
        y: WALL_SIZE + cel.row * CELL_SIZE + CELL_SIZE/2,
        col: cel.col,
        row: cel.row
    }));
    return posicoes;
}

function colisaoParede(x, y, larg, alt) {
    for (let p of paredes) {
        if (x < p[0] + p[2] && x + larg > p[0] && y < p[1] + p[3] && y + alt > p[1]) return true;
    }
    return false;
}

function verificarResposta() {
    const cx = jogador.x + jogador.largura/2;
    const cy = jogador.y + jogador.altura/2;
    for (let r of respostasPos) {
        if (cx > r.x - 35 && cx < r.x + 35 && cy > r.y - 16 && cy < r.y + 16) return r;
    }
    return null;
}

function verificarPorta() {
    const cx = jogador.x + jogador.largura/2;
    const cy = jogador.y + jogador.altura/2;
    const px = portaPos.x + portaPos.largura/2;
    const py = portaPos.y + portaPos.altura/2;
    return Math.hypot(cx - px, cy - py) < 55;
}

function verificarChave() {
    if (!chavePos.ativa) return false;
    const cx = jogador.x + jogador.largura/2;
    const cy = jogador.y + jogador.altura/2;
    const chaveCentroX = chavePos.x + 12;
    const chaveCentroY = chavePos.y + 12;
    if (Math.hypot(cx - chaveCentroX, cy - chaveCentroY) < 20) {
        chavePos.ativa = false;
        return true;
    }
    return false;
}

function mostrarFeedbackTexto(txt, cor) {
    const el = document.createElement('div');
    el.className = 'feedback';
    el.textContent = txt;
    el.style.color = cor;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 800);
}

function transicaoFase() {
    return new Promise(resolve => {
        const overlay = document.createElement('div');
        overlay.className = 'fade-transition';
        document.body.appendChild(overlay);
        setTimeout(() => overlay.classList.add('active'), 10);
        setTimeout(() => {
            overlay.remove();
            resolve();
        }, 500);
    });
}

function iniciarTimer() {
    if (intervaloId) clearInterval(intervaloId);
    tempoRestante = 50;
    atualizarTimerUI();
    intervaloId = setInterval(() => {
        if (!jogoAtivo || transicaoAtiva || faseVitoria) return;
        tempoRestante--;
        atualizarTimerUI();
        if (tempoRestante <= 0) {
            clearInterval(intervaloId);
            intervaloId = null;
            tempoEsgotado();
        }
    }, 1000);
}

function atualizarTimerUI() {
    let timerEl = document.getElementById('timer');
    if (!timerEl) {
        timerEl = document.createElement('div');
        timerEl.id = 'timer';
        timerEl.className = 'timer';
        const header = document.querySelector('.header');
        header.appendChild(timerEl);
    }
    timerEl.textContent = `⏱️ ${tempoRestante}s`;
    if (tempoRestante <= 10) {
        timerEl.classList.add('timer-warning');
    } else {
        timerEl.classList.remove('timer-warning');
    }
}

function tempoEsgotado() {
    if (!jogoAtivo || faseVitoria) return;
    mostrarFeedbackTexto("⏰ TEMPO ESGOTADO! Voltando ao início.", "#ff0000");
    jogador.x = posInicialJogador.x;
    jogador.y = posInicialJogador.y;
    respostaColetada = false;
    portaIbu = false;
    chaveObtida = false;
    chavePos.ativa = false;
    iniciarTimer();
}

function configurarObjetosFase(lab) {
    const temChave = (faseIndex === 2 || faseIndex === 4);
    if (temChave) {
        let inicioCelula = lab.posInicial;
        let portaCelula = lab.posPorta;
        let meioDistancia = (Math.abs(inicioCelula.col - portaCelula.col) + Math.abs(inicioCelula.row - portaCelula.row)) / 2;
        let celulasMeio = lab.celulasLivres.filter(cel => {
            let distInicio = Math.abs(cel.col - inicioCelula.col) + Math.abs(cel.row - inicioCelula.row);
            let distPorta = Math.abs(cel.col - portaCelula.col) + Math.abs(cel.row - portaCelula.row);
            let media = (distInicio + distPorta) / 2;
            return Math.abs(media - meioDistancia) <= 3;
        });
        let celEscolhida;
        if (celulasMeio.length > 0) {
            celulasMeio.sort((a, b) => {
                let distInicioA = Math.abs(a.col - inicioCelula.col) + Math.abs(a.row - inicioCelula.row);
                let distPortaA = Math.abs(a.col - portaCelula.col) + Math.abs(a.row - portaCelula.row);
                let distInicioB = Math.abs(b.col - inicioCelula.col) + Math.abs(b.row - inicioCelula.row);
                let distPortaB = Math.abs(b.col - portaCelula.col) + Math.abs(b.row - portaCelula.row);
                let mediaA = Math.abs((distInicioA + distPortaA) / 2 - meioDistancia);
                let mediaB = Math.abs((distInicioB + distPortaB) / 2 - meioDistancia);
                return mediaA - mediaB;
            });
            celEscolhida = celulasMeio[0];
        } else {
            celEscolhida = lab.celulasLivres[Math.floor(Math.random() * lab.celulasLivres.length)];
        }
        let chaveTamanho = 24;
        let chaveX = WALL_SIZE + celEscolhida.col * CELL_SIZE + (CELL_SIZE - chaveTamanho) / 2;
        let chaveY = WALL_SIZE + celEscolhida.row * CELL_SIZE + (CELL_SIZE - chaveTamanho) / 2;
        chavePos = { x: chaveX, y: chaveY, ativa: false };
        chaveObtida = false;
    } else {
        chavePos = { x: 0, y: 0, ativa: false };
    }
}

function criarFaseVitoria() {
    let paredesLista = [];
    paredesLista.push([0, 0, canvas.width, WALL_SIZE]);
    paredesLista.push([0, canvas.height - WALL_SIZE, canvas.width, WALL_SIZE]);
    paredesLista.push([0, 0, WALL_SIZE, canvas.height]);
    paredesLista.push([canvas.width - WALL_SIZE, 0, WALL_SIZE, canvas.height]);
    const btnW = 200, btnH = 60;
    const btnX = (canvas.width - btnW) / 2;
    const btnY = canvas.height / 2 + 30;
    vitoriaReiniciarArea = { x: btnX, y: btnY, w: btnW, h: btnH };
    let jogadorX = 60;
    let jogadorY = canvas.height - 100;
    return { paredes: paredesLista, jogadorX, jogadorY };
}

function reiniciarQuiz() {
    labCache = {};
    faseVitoria = false;
    jogoFinalizado = false;
    jogoAtivo = true;
    faseIndex = 0;
    if (intervaloId) clearInterval(intervaloId);
    const timerEl = document.getElementById('timer');
    if (timerEl) timerEl.remove();
    iniciarJogo();
}

async function avancarFase() {
    if (transicaoAtiva || faseVitoria || jogoFinalizado) return;
    transicaoAtiva = true;
    if (intervaloId) clearInterval(intervaloId);
    await transicaoFase();

    if (faseIndex === 0) {
        faseIndex = 1;
    } else if (faseIndex < 5) {
        faseIndex++;
    }

    if (faseIndex > 5) {
        faseVitoria = true;
        jogoFinalizado = true;
        const vitoria = criarFaseVitoria();
        paredes = vitoria.paredes;
        jogador.x = vitoria.jogadorX;
        jogador.y = vitoria.jogadorY;
        posInicialJogador = { x: jogador.x, y: jogador.y };
        questionEl.textContent = "🏆 VITÓRIA! 🏆";
        levelEl.textContent = "Fim de jogo";
        const timerEl = document.getElementById('timer');
        if (timerEl) timerEl.remove();
        transicaoAtiva = false;
        return;
    }

    faseVitoria = false;
    labAtual = obterLabirintoFixo(faseIndex);
    paredes = labAtual.paredes;
    gridLabirinto = labAtual.grid;
    celulasLivres = labAtual.celulasLivres;
    posInicialJogador = { x: labAtual.jogadorX, y: labAtual.jogadorY };
    jogador.x = labAtual.jogadorX;
    jogador.y = labAtual.jogadorY;
    posPortaPixel = { x: labAtual.portaPixel.x + (CELL_SIZE - 48) / 2, y: labAtual.portaPixel.y + (CELL_SIZE - 64) / 2 };
    portaPos = { x: posPortaPixel.x, y: posPortaPixel.y, largura: 48, altura: 64 };

    let posRespostas = posicionarRespostasEmBecos(celulasLivres, labAtual.posInicial, labAtual.posPorta);
    let respostasEmbaralhadas = [...perguntas[faseIndex-1].respostas];
    for (let i = respostasEmbaralhadas.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i+1));
        [respostasEmbaralhadas[i], respostasEmbaralhadas[j]] = [respostasEmbaralhadas[j], respostasEmbaralhadas[i]];
    }
    const respostaCorretaTexto = perguntas[faseIndex-1].respostas[perguntas[faseIndex-1].correta];
    respostasPos = [];
    for (let i = 0; i < 4; i++) {
        respostasPos.push({
            x: posRespostas[i].x, y: posRespostas[i].y,
            texto: respostasEmbaralhadas[i],
            correta: (respostasEmbaralhadas[i] === respostaCorretaTexto)
        });
    }

    configurarObjetosFase(labAtual);
    respostaColetada = false;
    portaIbu = false;
    questionEl.textContent = perguntas[faseIndex-1].pergunta;
    levelEl.textContent = `Fase ${faseIndex}/5`;

    iniciarTimer();

    if (faseIndex === 1) mostrarObjetivo("🎯 Explore os becos e encontre a resposta! (50s)", 4000);
    if (faseIndex === 2) mostrarObjetivo("🔑 Responda, depois pegue a chave no meio do labirinto! (50s)", 4000);
    if (faseIndex === 3) mostrarObjetivo("🎯 Explore os becos e encontre a resposta! (50s)", 4000);
    if (faseIndex === 4) mostrarObjetivo("🔑 Responda, depois pegue a chave no meio do labirinto! (50s)", 4000);
    if (faseIndex === 5) mostrarObjetivo("🏁 Última fase! Boa sorte! (50s)", 4000);
    transicaoAtiva = false;
}

function desenharMapa() {
    ctx.fillStyle = '#0a0a2a';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    for (let i = 0; i < 150; i++) {
        ctx.fillStyle = `rgba(255,255,255,${Math.random() * 0.4})`;
        ctx.fillRect(Math.random() * canvas.width, Math.random() * canvas.height, 2, 2);
    }
}

function desenharParedes() {
    for (let p of paredes) {
        ctx.fillStyle = '#4a6a3a';
        ctx.fillRect(p[0], p[1], p[2], p[3]);
        ctx.fillStyle = '#2a4a1a';
        ctx.fillRect(p[0] + 2, p[1] + 2, p[2] - 4, p[3] - 4);
        ctx.strokeStyle = '#ffd700';
        ctx.lineWidth = 1.5;
        ctx.strokeRect(p[0] + 1, p[1] + 1, p[2] - 2, p[3] - 2);
    }
}

function desenharJogador() {
    ctx.save();
    ctx.shadowBlur = 12;
    ctx.shadowColor = '#00aaff';
    ctx.fillStyle = '#ffffff';
    ctx.beginPath();
    ctx.ellipse(jogador.x + 11, jogador.y + 13, 9, 14, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = '#2277ff';
    ctx.beginPath();
    ctx.arc(jogador.x + 5, jogador.y + 6, 5, 0, Math.PI * 2);
    ctx.arc(jogador.x + 17, jogador.y + 6, 5, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = '#fff';
    ctx.beginPath();
    ctx.arc(jogador.x + 5, jogador.y + 6, 2, 0, Math.PI * 2);
    ctx.arc(jogador.x + 17, jogador.y + 6, 2, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = '#555';
    ctx.fillRect(jogador.x + 7, jogador.y + 21, 8, 12);
    ctx.restore();
}

function desenharRespostas() {
    for (let r of respostasPos) {
        ctx.save();
        ctx.shadowBlur = 6;
        ctx.shadowColor = '#0088ff';
        ctx.fillStyle = '#1e5faa';
        ctx.beginPath();
        ctx.roundRect(r.x - 35, r.y - 16, 70, 32, 8);
        ctx.fill();
        ctx.strokeStyle = '#44aaff';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.roundRect(r.x - 35, r.y - 16, 70, 32, 8);
        ctx.stroke();
        ctx.fillStyle = '#fff';
        ctx.font = 'bold 11px "Courier New"';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        let texto = r.texto;
        if (texto.length > 10) texto = texto.substring(0, 9) + ".";
        ctx.fillText(texto, r.x, r.y);
        ctx.restore();
    }
}

function desenharPorta() {
    ctx.fillStyle = '#8B5A2B';
    ctx.fillRect(portaPos.x, portaPos.y, portaPos.largura, portaPos.altura);
    ctx.fillStyle = '#D2B48C';
    ctx.fillRect(portaPos.x + 6, portaPos.y + 6, portaPos.largura - 12, portaPos.altura - 12);
    ctx.fillStyle = '#FFD700';
    ctx.fillRect(portaPos.x + 18, portaPos.y + 25, 12, 24);
}

function desenharChave() {
    if (!chavePos.ativa) return;
    ctx.fillStyle = '#FFD700';
    ctx.beginPath();
    ctx.arc(chavePos.x + 12, chavePos.y + 12, 9, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = '#B8860B';
    ctx.fillRect(chavePos.x + 9, chavePos.y + 1, 6, 10);
    ctx.fillStyle = '#FFF';
    ctx.font = 'bold 12px Arial';
    ctx.textAlign = 'center';
    ctx.fillText("🔑", chavePos.x + 12, chavePos.y + 13);
}

function desenharFaseVitoria() {
    ctx.save();
    ctx.shadowBlur = 20;
    ctx.shadowColor = '#FFD700';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.font = 'bold 64px "Courier New"';
    ctx.fillStyle = '#FFD700';
    ctx.fillText('🏆 VITÓRIA! 🏆', canvas.width/2, canvas.height/2 - 80);
    ctx.restore();

    ctx.font = '24px "Courier New"';
    ctx.fillStyle = '#FFF';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('Parabéns! Você completou todas as fases!', canvas.width/2, canvas.height/2 - 20);

    const btn = vitoriaReiniciarArea;
    ctx.save();
    ctx.shadowBlur = 10;
    ctx.shadowColor = '#00ff00';
    ctx.fillStyle = '#2a7a2a';
    ctx.beginPath();
    ctx.roundRect(btn.x, btn.y, btn.w, btn.h, 12);
    ctx.fill();
    ctx.strokeStyle = '#00ff00';
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.roundRect(btn.x, btn.y, btn.w, btn.h, 12);
    ctx.stroke();
    ctx.fillStyle = '#FFF';
    ctx.font = 'bold 28px "Courier New"';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('🔄 REINICIAR', btn.x + btn.w/2, btn.y + btn.h/2);
    ctx.restore();

    ctx.font = '16px "Courier New"';
    ctx.fillStyle = '#AAA';
    ctx.textAlign = 'center';
    ctx.fillText('Ande até o botão para reiniciar o jogo', canvas.width/2, btn.y + btn.h + 40);
}

function loopJogo() {
    if (!jogoAtivo) return;
    desenharMapa();
    desenharParedes();

    if (faseVitoria) {
        desenharFaseVitoria();
        const cx = jogador.x + jogador.largura/2;
        const cy = jogador.y + jogador.altura/2;
        const btn = vitoriaReiniciarArea;
        if (cx > btn.x && cx < btn.x + btn.w && cy > btn.y && cy < btn.y + btn.h) {
            reiniciarQuiz();
            return;
        }
        let nx = jogador.x, ny = jogador.y;
        if (teclas['ArrowUp'] || teclas['w'] || teclas['W']) ny -= jogador.velocidade;
        if (teclas['ArrowDown'] || teclas['s'] || teclas['S']) ny += jogador.velocidade;
        if (teclas['ArrowLeft'] || teclas['a'] || teclas['A']) nx -= jogador.velocidade;
        if (teclas['ArrowRight'] || teclas['d'] || teclas['D']) nx += jogador.velocidade;
        if (!colisaoParede(nx, jogador.y, jogador.largura, jogador.altura)) jogador.x = nx;
        if (!colisaoParede(jogador.x, ny, jogador.largura, jogador.altura)) jogador.y = ny;
        jogador.x = Math.max(10, Math.min(canvas.width - jogador.largura - 10, jogador.x));
        jogador.y = Math.max(10, Math.min(canvas.height - jogador.altura - 10, jogador.y));
        desenharJogador();
        animacaoId = requestAnimationFrame(loopJogo);
        return;
    }

    desenharRespostas();
    desenharPorta();
    if ((faseIndex === 2 || faseIndex === 4) && chavePos.ativa) desenharChave();
    desenharObjetivo();

    let nx = jogador.x, ny = jogador.y;
    if (teclas['ArrowUp'] || teclas['w'] || teclas['W']) ny -= jogador.velocidade;
    if (teclas['ArrowDown'] || teclas['s'] || teclas['S']) ny += jogador.velocidade;
    if (teclas['ArrowLeft'] || teclas['a'] || teclas['A']) nx -= jogador.velocidade;
    if (teclas['ArrowRight'] || teclas['d'] || teclas['D']) nx += jogador.velocidade;
    if (!colisaoParede(nx, jogador.y, jogador.largura, jogador.altura)) jogador.x = nx;
    if (!colisaoParede(jogador.x, ny, jogador.largura, jogador.altura)) jogador.y = ny;
    jogador.x = Math.max(10, Math.min(canvas.width - jogador.largura - 10, jogador.x));
    jogador.y = Math.max(10, Math.min(canvas.height - jogador.altura - 10, jogador.y));

    const resp = verificarResposta();
    if (resp && !respostaColetada) {
        if (resp.correta) {
            respostaColetada = true;
            if (faseIndex === 2 || faseIndex === 4) {
                chavePos.ativa = true;
                mostrarObjetivo("🔑 Resposta certa! Pegue a chave no meio do labirinto!", 4000);
            } else {
                portaIbu = true;
                mostrarObjetivo("🚪 Resposta certa! Vá até a porta!", 4000);
            }
            mostrarFeedbackTexto("✓ CORRETO!", "#00ff00");
        } else {
            mostrarFeedbackTexto("✗ ERRADO! Tente outra.", "#ff0000");
        }
    }
    if ((faseIndex === 2 || faseIndex === 4) && respostaColetada && !chaveObtida && verificarChave()) {
        chaveObtida = true;
        portaIbu = true;
        mostrarObjetivo("🚪 Chave obtida! Vá até a porta!", 4000);
    }
    if ((faseIndex === 1 || faseIndex === 3 || faseIndex === 5) && respostaColetada && !portaIbu) {
        portaIbu = true;
        mostrarObjetivo("🚪 Resposta certa! Vá até a porta!", 4000);
    }
    let podePassar = false;
    if ((faseIndex === 1 || faseIndex === 3 || faseIndex === 5) && respostaColetada) podePassar = true;
    if ((faseIndex === 2 || faseIndex === 4) && portaIbu && chaveObtida) podePassar = true;
    if (podePassar && verificarPorta()) avancarFase();
    desenharJogador();
    animacaoId = requestAnimationFrame(loopJogo);
}

CanvasRenderingContext2D.prototype.roundRect = function(x, y, w, h, r) {
    if (w < 2 * r) r = w / 2;
    if (h < 2 * r) r = h / 2;
    this.moveTo(x + r, y);
    this.lineTo(x + w - r, y);
    this.quadraticCurveTo(x + w, y, x + w, y + r);
    this.lineTo(x + w, y + h - r);
    this.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    this.lineTo(x + r, y + h);
    this.quadraticCurveTo(x, y + h, x, y + h - r);
    this.lineTo(x, y + r);
    this.quadraticCurveTo(x, y, x + r, y);
    return this;
};

document.addEventListener('keydown', e => {
    const k = e.key;
    if (k === 'ArrowUp' || k === 'ArrowDown' || k === 'ArrowLeft' || k === 'ArrowRight' ||
        k === 'w' || k === 'W' || k === 's' || k === 'S' || k === 'a' || k === 'A' || k === 'd' || k === 'D') {
        teclas[k] = true;
        e.preventDefault();
    }
});
document.addEventListener('keyup', e => {
    const k = e.key;
    if (k === 'ArrowUp' || k === 'ArrowDown' || k === 'ArrowLeft' || k === 'ArrowRight' ||
        k === 'w' || k === 'W' || k === 's' || k === 'S' || k === 'a' || k === 'A' || k === 'd' || k === 'D') {
        teclas[k] = false;
        e.preventDefault();
    }
});

window.iniciarJogo = async function() {
    document.getElementById('startScreen').style.display = 'none';
    jogoAtivo = true;
    faseVitoria = false;
    jogoFinalizado = false;
    faseIndex = 0;
    const sala = criarSalaPreparacao();
    paredes = sala.paredes;
    jogador.x = sala.jogadorX;
    jogador.y = sala.jogadorY;
    portaPos = sala.porta;
    questionEl.textContent = "SALA DE PREPARAÇÃO";
    levelEl.textContent = "Atravesse a porta para começar";
    mostrarObjetivo("🚪 Entre pela porta para iniciar a Fase 1", 4000);
    if (animacaoId) cancelAnimationFrame(animacaoId);
    loopJogo();
    function verificaPrep() {
        if (!jogoAtivo) return;
        if (verificarPorta()) avancarFase();
        else requestAnimationFrame(verificaPrep);
    }
    verificaPrep();
};